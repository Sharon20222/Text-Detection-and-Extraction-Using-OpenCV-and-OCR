from gettext import install
import cv2
import pytesseract
from langdetect import detect
from google.cloud import translate_v2 as translate
from transformers import pipeline

class TextDetector:
    def __init__(self, ocr_path=None, translation_api_key=None):
        if ocr_path:
            pytesseract.pytesseract.tesseract_cmd = ocr_path
        if translation_api_key:
            self.translate_client = translate.Client.from_service_account_json(translation_api_key)
        else:
            self.translate_client = None
        self.summarizer = pipeline("summarization")

    def preprocess_image(self, image_path):
        image = cv2.imread(image_path)
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary_image = cv2.threshold(gray_image, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        return binary_image

    def dilate_image(self, binary_image):
        structuring_element = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated_image = cv2.dilate(binary_image, structuring_element, iterations=1)
        return dilated_image

    def detect_contours(self, dilated_image):
        contours, _ = cv2.findContours(dilated_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours

    def extract_text_from_image(self, image, contours):
        text = ''
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            roi = image[y:y+h, x:x+w]
            extracted_text = pytesseract.image_to_string(roi)
            text += extracted_text + '\n'
        return text

    def detect_language(self, text):
        return detect(text)

    def translate_text(self, text, target_language):
        if self.translate_client:
            translation = self.translate_client.translate(text, target_language=target_language)
            return translation['translatedText']
        else:
            return text

    def summarize_text(self, text):
        summary = self.summarizer(text, max_length=130, min_length=30, do_sample=False)
        return summary[0]['summary_text']

    def process_image(self, image_path, operation=None, target_language=None):
        binary_image = self.preprocess_image(image_path)
        dilated_image = self.dilate_image(binary_image)
        contours = self.detect_contours(dilated_image)
        text = self.extract_text_from_image(binary_image, contours)
        
        detected_lang = self.detect_language(text)
        print(f"Detected language: {detected_lang}")

        if operation == 'translate' and target_language:
            text = self.translate_text(text, target_language)
        elif operation == 'summarize':
            text = self.summarize_text(text)
        elif operation == 'view':
            text = text
        
        return text, detected_lang
