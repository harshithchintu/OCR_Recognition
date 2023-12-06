import pytest
import requests_mock
import os
import json
import cv2
import getpass
from unittest.mock import patch, mock_open
import numpy as np
from opencv_with_users import upload_and_extract_content, capture_image, create_user, login, user_collection, client

TEST_OCR_API_KEY = os.getenv("API_KEY")
TEST_DATABASE_PATH = os.getenv("TEST_DATABASE")

# Create a test MongoDB client and set up the test database
test_client = client
test_db = test_client[TEST_DATABASE_PATH]
test_user_collection = test_db["test"]


@pytest.fixture
def setup_database():
    """
    Fixture to set up the test database before the test and clean it up afterward.
    """
    test_user_collection.delete_many({})
    user_collection.delete_many({})  # Clean the user collection

    yield test_user_collection, user_collection  # The test will run at this point

    # Clean up the database after the test runs
    test_user_collection.delete_many({})
    user_collection.delete_many({})


'''User Authentication Test Cases'''


# test case to create a new user
def test_create_user():
    test_username = "test_user_login"
    test_password = "test_password_login"
    created_user, _ = create_user(test_username, test_password)

    assert created_user == test_username


# Test case to login for an existing user
def test_login():
    # Create a test user
    test_username = "test_user_login1"
    test_password = "test_password_login1"
    create_user(test_username, test_password)

    # Call login() with correct credentials
    logged_in_user = login(test_username, test_password)

    # Verify the result
    assert logged_in_user == test_username


'''Test Cases using MOCK'''


# Test case for upload_and_extract_content with image URL
def test_upload_and_extract_content_with_url():
    """
    Test case for uploading and extracting content from an image URL using MOCK.
    """
    image_url = 'https://example.com/sample_image.jpg'
    with requests_mock.Mocker() as m:
        mock_response = {'ParsedResults': [{'ParsedText': 'Test content'}]}
        m.post('https://api.ocr.space/parse/image', json=mock_response)

        extracted_content = upload_and_extract_content(image_url=image_url, api_key=TEST_OCR_API_KEY)
        assert extracted_content == 'Test content'


# Test case for upload_and_extract_content with local file path
def test_upload_and_extract_content_with_local_file(tmp_path):
    """
    Test case for uploading and extracting content from a local file using MOCK.
    """
    local_file_path = os.path.join(tmp_path, 'test_image.jpg')
    cv2.imwrite(local_file_path, np.zeros((100, 100), dtype=np.uint8))  # Create a dummy image

    with requests_mock.Mocker() as m:
        mock_response = {'ParsedResults': [{'ParsedText': 'Test content'}]}
        m.post('https://api.ocr.space/parse/image', json=mock_response)

        extracted_content = upload_and_extract_content(local_file_path=local_file_path, api_key=TEST_OCR_API_KEY)
        assert extracted_content == 'Test content'


# Test case for upload_and_extract_content with API error
def test_upload_and_extract_content_api_error(requests_mock):
    """
    Test case for handling API error during upload_and_extract_content.
    """
    image_url = 'https://example.com/sample_image.jpg'
    requests_mock.post('https://api.ocr.space/parse/image', status_code=500, text='Internal Server Error')

    extracted_content = upload_and_extract_content(image_url=image_url, api_key=TEST_OCR_API_KEY)
    assert extracted_content is None


# Test case for upload_and_extract_content with invalid response structure
def test_upload_and_extract_content_invalid_response(requests_mock):
    """
    Test case for handling invalid response structure during upload_and_extract_content.
    """
    image_url = 'https://example.com/sample_image.jpg'
    mock_response = {'InvalidKey': 'InvalidValue'}
    requests_mock.post('https://api.ocr.space/parse/image', json=mock_response)

    extracted_content = upload_and_extract_content(image_url=image_url, api_key=TEST_OCR_API_KEY)
    assert extracted_content is None


# Test case for capture_image
def test_capture_image():
    """
    Test case for capturing an image.
    """
    captured_image = capture_image()
    assert captured_image is not None


'''Test cases that uses actual OCR'''


# Test case for ocr response verification
def test_valid_ocr_response():
    """
    Test case for verifying a valid OCR response.
    """
    image_path = "captured_image_test.jpg"
    api_key = TEST_OCR_API_KEY
    extracted_content = upload_and_extract_content(local_file_path=image_path, api_key=api_key)
    assert extracted_content == "Time is\r\n10 AM\r\n"


'''Test cases for Error Handling'''


# Test case for invalid API key
def test_invalid_api_key():
    """
    Test case for handling invalid API key.
    """
    image_path = "captured_image_test.jpg"
    api_key = 'xyz123'
    try:
        upload_and_extract_content(local_file_path=image_path, api_key=api_key)
    except ValueError as e:
        assert str(e) == "Invalid API key"


# Test case for validating API key
def test_missing_api_key():
    """
    Test case for handling missing API key.
    """
    with pytest.raises(ValueError, match="API key is required"):
        upload_and_extract_content(image_url="example.jpg", api_key=None)


# Test case for upload_and_extract_content with no image provided
def test_upload_and_extract_content_no_image():
    """
    Test case for handling upload_and_extract_content with no image provided.
    """
    with pytest.raises(ValueError, match="Either image URL or local file path must be provided"):
        extracted_content = upload_and_extract_content(api_key=TEST_OCR_API_KEY)
    # assert extracted_content is None


# Test case for upload_and_extract_content API response with unexpected status code
def test_upload_and_extract_content_unexpected_status_code(requests_mock):
    """
    Test case for handling upload_and_extract_content with unexpected status code.
    """
    image_url = 'https://example.com/sample_image.jpg'
    requests_mock.post('https://api.ocr.space/parse/image', status_code=403, text='Forbidden')
    extracted_content = upload_and_extract_content(image_url=image_url, api_key=TEST_OCR_API_KEY)
    assert extracted_content is None


'''Test Cases using Actual Database'''


# Test case to create a new user and verify it in the database
def test_create_user_and_verify_in_database():
    """
    Test case for creating a new user and verifying it in the database.
    """
    new_username = "test_user_db"
    new_password = "test_password_db"

    # Ensure the user does not exist before creating
    existing_user = user_collection.find_one({"username": new_username})
    assert existing_user is None

    # Create a new user
    create_user(new_username, new_password)

    # Verify that the user now exists in the database
    created_user = user_collection.find_one({"username": new_username})
    assert created_user is not None
    assert created_user["password"] == new_password


# Test case to create a new user and attempt to create a duplicate
def test_create_user_duplicate(setup_database):
    existing_username = "existing_user_db"
    existing_password = "existing_password_db"

    # Ensure the user does not exist before creating
    existing_user = user_collection.find_one({"username": existing_username})
    assert existing_user is None

    # Create a new user
    create_user(existing_username, existing_password)

    # Attempt to create the same user again and verify it fails
    with pytest.raises(RuntimeError, match="User already exists."):
        create_user(existing_username, "new_password")


# Test case for ocr response verification and adding content to the database
def test_valid_ocr_response_and_add_to_db():
    """
    Test case for verifying a valid OCR response and adding the content to the database.
    """
    image_path = "captured_image_test.jpg"
    api_key = TEST_OCR_API_KEY

    # Perform OCR and extract content
    extracted_content = upload_and_extract_content(local_file_path=image_path, api_key=api_key)

    # Verify the extracted content
    assert extracted_content == "Time is\r\n10 AM\r\n"

    # Add the extracted content to the database
    username = "test_user_db_with_content"
    password = "test_password_db_with_content"

    # Ensure the user does not exist before creating
    existing_user = user_collection.find_one({"username": username})
    assert existing_user is None

    # Create a new user
    create_user(username, password)

    # Add the extracted content to the user's data in the database
    user_collection.update_one({"username": username}, {"$set": {"extracted_content": extracted_content}})

    # Verify that the user and the extracted content now exist in the database
    user_with_content = user_collection.find_one({"username": username})
    assert user_with_content is not None
    assert user_with_content["password"] == password
    assert user_with_content["extracted_content"] == extracted_content


# Test case for login with correct credentials
def test_login_correct_credentials():
    username = "test_login_user"
    password = "test_login_password"

    # Create the user
    create_user(username, password)

    # Login with correct credentials
    logged_in_user = login(username, password)
    assert logged_in_user == username


# Test case for login with incorrect password
# def test_login_incorrect_password():
#     username = "test_incorrect_password_user"
#     password = "test_incorrect_password"
#
#     # Create the user
#     create_user(username, password)
#
#     # Attempt to login with incorrect password
#     with pytest.raises(RuntimeError, match="Unauthorized. Please check your username and password."):
#         login(username, "incorrect_password")


# Test case for login with non-existent user
# def test_login_nonexistent_user():
#     username = "nonexistent_user"
#
#     # Attempt to login with a user that does not exist
#     with pytest.raises(RuntimeError, match="Unauthorized. Please check your username and password."):
#         login(username, "password")


# Ensure to close the MongoDB client after running the tests
def teardown():
    client.close()


if __name__ == '__main__':
    pytest.main()
