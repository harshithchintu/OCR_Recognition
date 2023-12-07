import os
import cv2
import requests
import re
import json
import getpass
import error_handler
from dotenv import load_dotenv
from pymongo import MongoClient
import test_pytestcv

# Load environment variable from .env file
current_path = os.path.dirname(__file__)
dotenv_filename = os.path.join(current_path, ".env")
load_dotenv(dotenv_path=dotenv_filename)
ocr_space_api_key = os.getenv("API_KEY")
ocr_url = os.getenv("OCR_URL")
MONGO_URI = os.getenv("MONGO_URI")
USER_DATABASE_PATH = os.getenv("DATABASE")

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client[USER_DATABASE_PATH]
user_collection = db["users"]


def upload_and_extract_content(image_url=None, local_file_path=None, api_key=None, language='eng'):
    """
    Uploads an image (either from a URL or a local file), performs OCR, and extracts content.

    Args:
        image_url (str): URL of the image to be processed.
        local_file_path (str): Local file path of the image to be processed.
        api_key (str): API key.
        language (str): OCR language (default is 'eng' for English).

    Returns:
        str: Extracted text content from the image.

    Raises:
        ValueError: If API key is not provided or if neither image URL nor local file path is provided.
    """
    # error handling for api
    if not api_key:
        raise ValueError("API key is required")
    # error handling for image
    if not image_url and not local_file_path:
        raise ValueError("Either image URL or local file path must be provided")

    if local_file_path:
        with open(local_file_path, 'rb') as file:
            files = {'file': file}
            response = requests.post(ocr_url, files=files,
                                     data={'apikey': api_key, 'language': language})
    else:
        payload = {
            'url': image_url,
            'apikey': api_key,
            'language': language,
        }
        response = requests.post(ocr_url, data=payload)

    if response.status_code == 200:
        error_handler.SUCCESS
    elif response.status_code == 400:
        error_handler.BAD_REQUEST
    else:
        error_handler.SERVER_ERROR
        return None
    result = response.json()
    # Check if the response is valid.
    if 'ParsedResults' not in result or not result['ParsedResults']:
        print('Invalid response structure:', result)
        return None
    text = result['ParsedResults'][0]['ParsedText']
    return text


def capture_image():
    """
    Captures an image from the webcam or connected camera device.

    Returns:
        numpy.ndarray: Captured image as a NumPy array.

    Raises:
        RuntimeError: If the camera cannot be opened or if a frame cannot be read.
    """
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError("Could not open camera.")
        ret, frame = cap.read()
        if not ret:
            raise RuntimeError("Could not read frame.")
        cap.release()
        return frame
    except Exception as e:
        print(f"Error: {e}")
        return None


def create_user(user_input=None, password_input=None):
    """
    Creates a new user and adds their credentials to the database.

    Args:
        user_input (str): Username provided by the user.
        password_input (str): Password provided by the user.

    Returns:
        tuple or None: Tuple containing username and password if user creation is successful, else None.

    Raises:
        RuntimeError: If the specified username already exists in the user database.
    """
    try:
        username = user_input or input("Enter your username: ")
        password = password_input or getpass.getpass("Enter your password: ")
        # Load existing user data from the database
        # Check if the username already exists in MongoDB
        if user_collection.find_one({"username": username}):
            raise RuntimeError("User already exists.")

        # Add the new user to the MongoDB collection
        user_data = {"username": username, "password": password}
        user_collection.insert_one(user_data)
        print("User created successfully.")
        return username, password
    except Exception as e:
        print(f"Error: {e}")
        raise RuntimeError("User already exists.")


def login(user_input=None, password_input=None, input_function=input):
    """
    Logs in an existing user by verifying their credentials against the database.

    Args:
        input_function: For testing
        user_input (str): Username provided by the user.
        password_input (str): Password provided by the user.

    Returns:
        str: Username of the logged-in user.

    Raises:
        FileNotFoundError: If the user database file is not found.
        RuntimeError: If the provided username and password do not match any existing user.
    """
    while True:
        if test_pytestcv.test_login:
            username = user_input or input_function
        username = user_input or input("Enter your username: ")
        password = password_input or getpass.getpass("Enter your password: ")

        # Check if the entered username and password are correct
        user_data = user_collection.find_one({"username": username, "password": password})
        if user_data:
            print("Login successful.")
            return username
        else:
            print("Unauthorized. Please check your username and password.")


if __name__ == '__main__':
    # Ask the user to log in or create a new account
    user_choice = input("Do you want to (L)ogin or (C)reate a new account? ").upper()

    try:
        if user_choice == 'L':
            username = login()
        elif user_choice == 'C':
            username, password = create_user()
        else:
            print("Invalid choice. Exiting.")
            exit()

        user_data = {user["username"]: {"password": user["password"]} for user in user_collection.find()}

        # Capture an image from the webcam
        captured_image = capture_image()

        if captured_image is not None:
            # Display the captured image
            cv2.imshow('Captured Image', captured_image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

            # Save the captured image to a file
            cv2.imwrite('captured_image.jpg', captured_image)

            # Extract content from the captured image
            extracted_content = upload_and_extract_content(local_file_path='captured_image.jpg',
                                                           api_key=ocr_space_api_key)

            if extracted_content is not None:
                cleaned_content = extracted_content.replace('\n', '').replace('\r', '')
                extracted_array_content = {"text": cleaned_content}
                user_collection.update_one({"username": username}, {"$push": {"extracted_content": extracted_array_content}})
                # Identify words and integers using regular expressions
                words = re.findall(r'\b[A-Za-z]+\b', extracted_content)
                integers = re.findall(r'\b\d+\b', extracted_content)

                # Display and print the identified words and integers
                print('Extracted Content: ', extracted_content)
                print('Extracted Words:', words)
                print('Extracted Integers:', integers)
            else:
                print('Failed to extract content.')

        else:
            print('Failed to capture an image.')

    except Exception as e:
        print(f"Error: {e}")
        exit()
