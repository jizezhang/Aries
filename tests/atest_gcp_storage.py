"""Contains tests for the Google Cloud (gcp) storage module.
"""
import logging
import unittest

import os
import sys
aries_parent = os.path.join(os.path.dirname(__file__), "..", "..")
if aries_parent not in sys.path:
    sys.path.append(aries_parent)
from Aries.gcp.storage import GSObject, GSFolder, GSFile
from Aries.strings import Base64String
logger = logging.getLogger(__name__)


def setUpModule():
    """Configures the Google Application Credentials

    The test environment may store the content of the JSON key-file in "GOOGLE_CREDENTIALS".
    This function decodes and saves the JSON key-file into the local file system.

    """
    test_dir = os.path.dirname(__file__)
    json_file = os.path.join(test_dir, "..", "private", "gcp.json")
    # Use the b64 encoded content as credentials if "GOOGLE_CREDENTIALS" is set.
    credentials = os.environ.get("GOOGLE_CREDENTIALS")
    if credentials and credentials.startswith("ew"):
        if not os.path.exists(json_file):
            Base64String(credentials).decode_to_file(json_file)
    # Set "GOOGLE_APPLICATION_CREDENTIALS" if json file exists.
    if os.path.exists(json_file):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = json_file


class TestGCStorage(unittest.TestCase):
    """Contains test cases for Google Cloud Platform Storage.
    """
    @classmethod
    def setUpClass(cls):
        GSFolder("gs://aries_test/copy_test/").delete()

    def setUp(self):
        # Skip test if "GOOGLE_APPLICATION_CREDENTIALS" is not found.
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            self.skipTest("GCP Credentials not found.")

    def test_parse_uri(self):
        """Tests parsing GCS URI
        """
        # Bucket root without "/"
        gs_obj = GSObject("gs://aries_test")
        self.assertEqual(gs_obj.bucket_name, "aries_test")
        self.assertEqual(gs_obj.prefix, "")
        # Bucket root with "/"
        gs_obj = GSObject("gs://aries_test/")
        self.assertEqual(gs_obj.bucket_name, "aries_test")
        self.assertEqual(gs_obj.prefix, "")
        # Object without "/"
        gs_obj = GSObject("gs://aries_test/test_folder")
        self.assertEqual(gs_obj.bucket_name, "aries_test")
        self.assertEqual(gs_obj.prefix, "test_folder")
        # Object with "/"
        gs_obj = GSObject("gs://aries_test/test_folder/")
        self.assertEqual(gs_obj.bucket_name, "aries_test")
        self.assertEqual(gs_obj.prefix, "test_folder/")
        # Folder without "/"
        gs_obj = GSFolder("gs://aries_test/test_folder")
        self.assertEqual(gs_obj.uri, "gs://aries_test/test_folder")
        self.assertEqual(gs_obj.bucket_name, "aries_test")
        self.assertEqual(gs_obj.prefix, "test_folder/")

    def test_bucket_root(self):
        """Tests accessing google cloud storage bucket root.
        """
        # Access the bucket root
        self.assert_bucket_root("gs://aries_test")
        self.assert_bucket_root("gs://aries_test/")

    def assert_bucket_root(self, gs_path):
        """Checks if the bucket root contains the expected folder and files.
        
        Args:
            gs_path (str): Google cloud storage path to the bucket root, e.g. "gs://bucket_name".
        """
        parent = GSFolder(gs_path)
        # Test listing the folders
        folders = parent.folders
        self.assertEqual(len(folders), 1)
        self.assertTrue(isinstance(folders[0], GSFolder), "Type: %s" % type(folders[0]))
        self.assertEqual(folders[0].uri, "gs://aries_test/test_folder/")
        # Test listing the files
        files = parent.files
        self.assertEqual(len(files), 2)
        for file in files:
            self.assertTrue(isinstance(file, GSFile), "Type: %s" % type(file))
            self.assertIn(file.uri, [
                "gs://aries_test/file_in_root.txt",
                "gs://aries_test/test_folder"
            ])

    def test_gs_folder(self):
        """Tests accessing a Google Cloud Storage folder.
        """
        # Access a folder in a bucket
        self.assert_gs_folder("gs://aries_test/test_folder")
        self.assert_gs_folder("gs://aries_test/test_folder/")

    def assert_gs_folder(self, gs_path):
        """Checks if a Google Cloud Storage folder contains the expected folders and files.
        
        Args:
            gs_path ([type]): [description]
        """
        # Test listing the folders
        parent = GSFolder(gs_path)
        folders = parent.get_folders()
        self.assertEqual(len(folders), 1)
        self.assertEqual(folders[0], "gs://aries_test/test_folder/test_subfolder/")
        names = parent.folder_names
        self.assertEqual(len(folders), 1)
        self.assertEqual(names[0], "test_subfolder")
        # Test listing the files
        files = parent.files
        self.assertEqual(len(files), 1)
        self.assertTrue(isinstance(files[0], GSFile), "Type: %s" % type(files[0]))
        self.assertEqual(files[0].uri, "gs://aries_test/test_folder/file_in_folder.txt")
        names = parent.file_names
        self.assertEqual(len(folders), 1)
        self.assertEqual(names[0], "file_in_folder.txt")

    def test_gs_file(self):
        """Tests accessing a Google Cloud Storage file.
        """
        # Test the blob property
        # File exists
        gs_file_exists = GSFile("gs://aries_test/file_in_root.txt")
        self.assertTrue(gs_file_exists.blob.exists())
        # File does not exists
        gs_file_null = GSFile("gs://aries_test/abc.txt")
        self.assertFalse(gs_file_null.blob.exists())

        # Test the read() method
        self.assertEqual(gs_file_exists.read(), b'This is a file in the bucket root.')
        self.assertIsNone(gs_file_null.read())

    def test_copy_and_delete_folder(self):
        source_path = "gs://aries_test/test_folder/"
        # Destination path ends with "/", the original folder name will be preserved.
        dest_path = "gs://aries_test/copy_test/"
        folder = GSFolder(source_path)
        folder.copy(dest_path)
        copied = GSFolder(dest_path)
        self.assertEqual(len(copied.files), 0)
        self.assertEqual(len(copied.folders), 1)
        self.assertEqual(len(copied.blobs()), 4, [b.name for b in copied.blobs()])
        self.assertEqual(copied.folder_names[0], "test_folder")
        # Delete the copied files
        copied.delete()
        self.assertEqual(len(copied.files), 0)
        self.assertEqual(len(copied.folders), 0)

        # Destination path does not end with "/", the original folder will be renamed.
        dest_path = "gs://aries_test/copy_test/new_name"
        folder = GSFolder(source_path)
        folder.copy(dest_path)
        copied = GSFolder(dest_path)
        self.assertEqual(len(copied.files), 1)
        self.assertEqual(len(copied.folders), 1)
        self.assertEqual(len(copied.blobs()), 4, [b.name for b in copied.blobs()])
        self.assertEqual(copied.folder_names[0], "test_subfolder")
        # Delete the copied files
        GSFolder("gs://aries_test/copy_test/").delete()

    def test_copy_and_delete_prefix(self):
        # Copy a set of objects using the prefix
        source_path = "gs://aries_test/test_folder"
        dest_path = "gs://aries_test/copy_test/"
        objects = GSObject(source_path)
        objects.copy(dest_path)
        copied = GSFolder(dest_path)
        self.assertEqual(len(copied.files), 1)
        self.assertEqual(len(copied.folders), 1)
        self.assertEqual(len(copied.blobs()), 5, [b.name for b in copied.blobs()])
        self.assertEqual(copied.folder_names[0], "test_folder")
        # Delete the copied files
        GSFolder("gs://aries_test/copy_test/").delete()

    def test_copy_to_root_and_delete(self):
        # Destination is the bucket root, whether it ends with "/" does not matter.
        source_path = "gs://aries_test/test_folder"
        # Without "/"
        source_path = "gs://aries_test/test_folder/test_subfolder"
        dest_path = "gs://aries_test"
        folder = GSFolder(source_path)
        folder.copy(dest_path)
        copied = GSFolder("gs://aries_test/test_subfolder/")
        self.assertEqual(len(copied.files), 1)
        self.assertEqual(len(copied.folders), 0)
        self.assertEqual(len(copied.blobs()), 2, [b.name for b in copied.blobs()])
        self.assertEqual(copied.file_names[0], "file_in_subfolder.txt")
        # Delete the copied files
        GSFolder("gs://aries_test/test_subfolder/").delete()
        # With "/"
        source_path = "gs://aries_test/test_folder/test_subfolder"
        dest_path = "gs://aries_test/"
        folder = GSFolder(source_path)
        folder.copy(dest_path)
        copied = GSFolder("gs://aries_test/test_subfolder/")
        self.assertEqual(len(copied.files), 1)
        self.assertEqual(len(copied.folders), 0)
        self.assertEqual(len(copied.blobs()), 2, [b.name for b in copied.blobs()])
        self.assertEqual(copied.file_names[0], "file_in_subfolder.txt")
        # Delete the copied files
        GSFolder("gs://aries_test/test_subfolder/").delete()

    def test_upload_from_file(self):
        gs_file = GSFile("gs://aries_test/local_upload.txt")
        # Try to upload a file that does not exist.
        local_file_non_exist = os.path.join(os.path.dirname(__file__), "abc.txt")
        with self.assertRaises(FileNotFoundError):
            gs_file.upload_from_file(local_file_non_exist)
        # Upload a file and check the content.
        local_file = os.path.join(os.path.dirname(__file__), "fixtures", "test_file.txt")
        gs_file.upload_from_file(local_file)
        self.assertEqual(gs_file.read(), b'This is a local test file.\n')
        gs_file.delete()

    def test_create_blob(self):
        gs_file = GSFile("gs://aries_test/new_file.txt")
        self.assertFalse(gs_file.blob.exists())
        gs_file.create()
        self.assertTrue(gs_file.blob.exists())
        gs_file.delete()
