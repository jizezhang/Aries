"""Contains classes for manipulating Google Cloud Storage Objects.

If you are not running in Google Compute Engine or App Engine,
authentication to Google Cloud Platform is required in order to use this module.

Authentication can be done by setting the "GOOGLE_APPLICATION_CREDENTIALS" environment variable 
to JSON key-file. 
In command line:
    $ export GOOGLE_APPLICATION_CREDENTIALS="/path/to/keyfile.json"
In python:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/keyfile.json"

See Also: https://googleapis.github.io/google-cloud-python/latest/core/auth.html

"""
import os
import binascii
import logging
from tempfile import NamedTemporaryFile
from google.cloud import storage
from ..storage import StorageObject, StorageFolder, StorageFile
logger = logging.getLogger(__name__)


class GSObject(StorageObject):
    """The base class for Google Storage Object.

    Attributes:
        prefix: The Google Cloud Storage prefix, which is the path without the beginning "/"
    """
    def __init__(self, gs_path):
        """Initializes a Google Cloud Storage Object.

        Args:
            gs_path: The path of the object, e.g. "gs://bucket_name/path/to/file.txt".

        """
        super(GSObject, self).__init__(gs_path)
        self._client = storage.Client()
        self._bucket = None
        # The "prefix" for gcs does not include the beginning "/"
        if self.path.startswith("/"):
            self.prefix = self.path[1:]
        else:
            self.prefix = self.path

    def __getattribute__(self, item):
        
        return super(GSObject, self).__getattribute__(item)

    @property
    def bucket_name(self):
        """The name of the Google Cloud Storage bucket as a string."""
        return self.hostname

    @property
    def client(self):
        return self._client
            
    def _get_bucket(self):
        self._bucket = self.client.get_bucket(self.bucket_name)

    @property
    def bucket(self):
        if not self._bucket:
            self._get_bucket()
        return self._bucket

    @property
    def gs_path(self):
        return self.uri

    def blobs(self, delimiter=None):
        """Gets the blobs in the bucket having the prefix.

        The returning list will contain object in the folder and all sub-folders

        Args:
            delimiter: Use this to emulate hierarchy.
            If delimiter is None, the returning list will contain objects in the folder and in all sub-directories.
            Set delimiter to "/" to eliminate files in sub-directories.

        Returns: A list of GCS blobs.

        See Also: https://googleapis.github.io/google-cloud-python/latest/storage/blobs.html

        """
        return list(self.bucket.list_blobs(prefix=self.prefix, delimiter=delimiter))

    def delete(self):
        """Deletes all objects with the same prefix."""
        # This needs to be done before the batch.
        blobs = self.blobs()
        if blobs:
            with self.client.batch():
                for blob in blobs:
                    blob.delete()

    def copy(self, to):
        """Copies folder/file in a Google Cloud storage directory to another one.

        Args:
            to (str): Destination Google Cloud Storage path.
            If the path ends with "/", e.g. "gs://bucket_name/folder_name/",
                the folder/file will be copied under the destination folder with the original name.
            If the path does not end with "/", e.g. "gs://bucket_name/new_name",
                the folder/file will be copied and renamed to the "new_name".

        Returns: None

        Example:
            GSFolder("gs://bucket_a/a/b/c/").copy("gs://bucket_b/x/y/z") will copy the following files
                gs://bucket_a/a/b/c/d/example.txt
                gs://bucket_a/a/b/c/example.txt
            to
                gs://bucket_b/x/y/z/d/example.txt
                gs://bucket_b/x/y/z/example.txt

        """
        # Check if the destination is a bucket root.
        # Prefix will be empty if destination is bucket root.
        # Always append "/" to bucket root.
        if not GSObject(to).prefix and not to.endswith("/"):
            to += "/"

        if self.prefix.endswith("/"):
            # The source is a folder if its prefix ends with "/"
            if to.endswith("/"):
                # If the destination ends with "/",
                # copy the folder under the destination
                to += self.name + "/"
            else:
                # If the destination does not end with "/",
                # rename the folder.
                to += "/"
        else:
            # Otherwise, it can be a file or an object or a set of filtered objects.
            if to.endswith("/"):
                # If the destination ends with "/",
                # copy all objects under the destination
                to += self.name
            else:
                # If the destination does not end with "/",
                # simply replace the prefix.
                pass

        destination = GSObject(to)

        source_files = self.blobs()
        with self.client.batch():
            for blob in source_files:
                new_name = str(blob.name).replace(self.prefix, destination.prefix, 1)
                if new_name != str(blob.name):
                    self.bucket.copy_blob(blob, destination.bucket, new_name)

        logger.debug("%d blobs copied" % len(source_files))

    def move(self, to):
        """Moves the objects to another location."""
        self.copy(to)
        self.delete()


class GSFolder(GSObject, StorageFolder):
    """Represents a Google Cloud Storage Folder

    Method Resolution Order: GSFolder, GSObject, StorageFolder, StorageObject
    """

    def __init__(self, gs_path):
        """Initializes a Google Cloud Storage Directory.

        Args:
            gs_path: The path of the object, e.g. "gs://bucket_name/path/to/dir/".

        """
        # super() will call the __init__() of StorageObject, StorageFolder and GSObject
        super(GSFolder, self).__init__(gs_path)

        # Make sure prefix ends with "/", otherwise it is not a "folder"
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"

    @property
    def folders(self):
        iterator = self.bucket.list_blobs(prefix=self.prefix, delimiter='/')
        list(iterator)
        return [
            GSFolder("gs://%s/%s" % (self.bucket_name, p))
            for p in iterator.prefixes
        ]

    @property
    def files(self):
        return [
            GSFile("gs://%s/%s" % (self.bucket_name, b.name))
            for b in self.bucket.list_blobs(prefix=self.prefix, delimiter='/')
            if not b.name.endswith("/")
        ]

    @property
    def size(self):
        size_bytes = 0
        # Total size of files and folders
        for c in [self.files, self.folders]:
            for f in c:
                s = f.size
                if not s:
                    continue
                size_bytes += s
        logger.debug("%s %s Bytes." % (self.path, size_bytes))
        return size_bytes


class GSFile(GSObject, StorageFile):
    def __init__(self, gs_path):
        """

        Args:
            gs_path:

        """
        # super() will call the __init__() of StorageObject, StorageFolder and GSObject
        super(GSFile, self).__init__(gs_path)
        self.__blob = None
        self.__offset = 0
        self.__closed = True
        self.__buffer = None
        self.__buffer_offset = None
        self.__temp_file = None
        self.__gz = None

    @property
    def blob(self):
        """Gets or initialize a Google Cloud Storage Blob.

        Returns: A Google Cloud Storage Blob object.
            Use blob.exists() to determine whether or not the blob exists.

        """
        if self.__blob is None:
            self.__blob = self.__get_or_init_blob()
        return self.__blob

    @property

    def file_size(self):
        return self.blob.size

    def __get_or_init_blob(self):
        """Gets or initialize a Google Cloud Storage Blob.

        Returns: A Google Cloud Storage Blob object.
            Use blob.exists() to determine whether or not the blob exists.

        """
        file_blob = self.bucket.get_blob(self.prefix)
        if file_blob is None:
            # This will not make an HTTP request.
            # It simply instantiates a blob object owned by this bucket.
            # See https://googleapis.github.io/google-cloud-python/latest/storage/buckets.html
            # #google.cloud.storage.bucket.Bucket.blob
            file_blob = self.bucket.blob(self.prefix)
        return file_blob

    def upload_from_file(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError("File not found: %s" % file_path)

        with open(file_path, 'rb') as f:
            self.blob.upload_from_file(f)
        return True

    def create(self):
        """Creates an empty file, if the file does not exist.

        Returns:
            Blob: The Google Cloud Storage blob.
        """
        blob = storage.Blob(self.prefix, self.bucket)
        if not blob.exists():
            blob.upload_from_string("")
        return blob

    def is_gz(self):
        if self.__gz is None:
            if self.blob.size < 2:
                return False
            offset = self.tell()
            self.seek(0)
            b = binascii.hexlify(self.read(2))
            logger.debug("File begins with: %s" % b)
            self.seek(offset)
            self.__gz = b == b'1f8b'
        return self.__gz

    # The following implements the IOBase interface.
    # For seeking
    def seek(self, pos, whence=0):
        """Changes the read beginning position to byte offset pos.
        Args:
            pos (int): The number of bytes.
            whence (int):
                * 0 -- start of stream (the default); offset should be zero or positive
                * 1 -- current stream position; offset may be negative
                * 2 -- end of stream; offset is usually negative

        Returns:

        """
        # Run __append() to save and clear the buffer
        if self.__buffer:
            self.__append()

        if whence == 0:
            self.__offset = pos
        elif whence == 1:
            self.__offset += pos
        elif whence == 2:
            self.__offset = self.file_size + pos
        else:
            raise ValueError("whence must be 0, 1 or 2.")
        return self.__offset

    def tell(self):
        """Returns an int indicating the current stream position."""
        return self.__offset

    def seekable(self):
        return True

    # For reading
    def read(self, size=None):
        """Reads the file from the Google Cloud bucket to memory

        Returns: Bytes containing the contents of the file.
        """
        # Read data from temp file if it exist.
        if self.__temp_file:
            with open(self.__temp_file) as f:
                f.seek(self.__offset)
                b = f.read(size)
                self.__offset = f.tell()
                return b
        elif self.blob.exists():
            # Read data from bucket
            blob_size = self.blob.size
            if not size:
                end = blob_size - 1
            else:
                end = self.__offset + size - 1
            if end >= blob_size - 1:
                end = None
            logger.debug("Reading from %s to %s" % (self.__offset, end))
            b = self.blob.download_as_string(start=self.__offset, end=end)
            if end:
                self.__offset = end + 1
            else:
                self.__offset = blob_size
            return b
        else:
            return None

    def readable(self):
        return True

    # For writing
    def __append(self):
        """Appends the data from buffer to temp file.
        """
        # Do nothing if there is no buffer.
        if not self.__buffer:
            return
        # Create a temp file if it does not exist.
        if not self.__temp_file:
            f = NamedTemporaryFile(delete=False)
            self.__temp_file = f.name
            # Download the blob to temp file if it exists.
            if self.blob.exists():
                self.blob.download_to_file(f)
        else:
            # Open existing temp file.
            f = open(self.__temp_file, 'w+b')
            f.seek(self.__buffer_offset)
        if isinstance(self.__buffer, str):
            b = self.__buffer.encode()
        else:
            b = self.__buffer
        f.write(b)
        self.__buffer = None
        self.__buffer_offset = None
        self.__offset += len(b)
        f.close()

    def write(self, b):
        if self.closed:
            raise ValueError("write to closed file")
        if self.__buffer is None:
            self.__buffer_offset = self.__offset
            self.__buffer = b
        else:
            self.__buffer += b
        # Append the buffer to temp file if size is greater than 1MB
        buffer_size = len(self.__buffer)
        if buffer_size > 1024 * 1024:
            self.__append()
        self.__offset += len(b)
        return len(b)

    def flush(self):
        """Flush write buffers and upload the data to bucket.
        """
        self.__append()
        if self.__temp_file:
            self.blob.upload_from_filename(self.__temp_file)

    def close(self):
        """Flush and close the file.
        This method has no effect if the file is already closed.
        """
        if self.__closed:
            return
        try:
            self.flush()
        finally:
            # Remove __temp_file if it exists.
            if self.__temp_file:
                os.unlink(self.__temp_file)
                self.__temp_file = None
            self.__buffer = None
            # Set __closed attribute
            self.__closed = True

    def writable(self):
        return True

    def open(self):
        self.__closed = False
        self.__buffer = None
        return self

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return
