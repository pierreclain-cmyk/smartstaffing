#!/usr/bin/env bash
# Installation de Tesseract OCR pour la lecture d'images sur Render
apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-fra
pip install -r requirements.txt
