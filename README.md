SHOPIFY PRODUCT TAXONOMY CLASSIFIER (DJANGO PROTOTYPE):

This project is a Django-based prototype that classifies products from an Excel catalogue into Shopify Product Taxonomy categories. It was built as part of a Python Developer technical assignment.s
The application imports products from an Excel file, predicts a category, calculates a confidence score, suggests alternative categories when confidence is low, and provides a simple dashboard to review the results.

Features

Import products from Product List.xlsx
Shopify taxonomy-based category matching (prototype subset)
Confidence score for each prediction
Alternative category suggestions
Manual review for low-confidence results
Handles products with missing descriptions or images
REST API for viewing products and classifications
Simple dashboard for reviewing results

Technologies Used

Python 3.13
Django 5
Django REST Framework
SQLite (development)
MariaDB-ready configuration
Pillow
scikit-learn

Project Structure

django_prototype/ │── classifier/ │── config/ │── templates/ │── manage.py │── requirements.txt │── Product List.xlsx

Setup

1. Navigate into the project folder
cd django_prototype_v2
2. Create and activate a virtual environment (skip if you already made one)
python -m venv venv
venv\Scripts\Activate.ps1
3. Install dependencies (retry with longer timeout if it fails on a slow connection)
pip install -r requirements.txt --timeout 120 --retries 5
4. Generate and apply migrations
python manage.py makemigrations classifier
python manage.py migrate
5. Load the taxonomy reference data into the database
python manage.py seed_taxonomy
6. Import and classify your product catalogue (fast, text-only run)
python manage.py classify_catalogue "Product List.xlsx" --limit 5000
7. Start the server
python manage.py runserver


Classification Approach

The prototype combines several signals to determine the most suitable category:
Product title
Product description
Brand (when available)
Product type (when available)
Image information (when available)
The final confidence score is used to decide whether a product can be automatically classified or should be sent for manual review.

Error Handling

The application is designed to continue processing even if individual products contain missing data or image-related issues. Products that cannot be classified confidently are marked for manual review instead of stopping the entire batch.

Current Limitations

Uses a prototype subset of the Shopify taxonomy.
Image-based category classification is optional and not enabled by default.
SQLite is used for local development; MariaDB can be used for production.

Future Improvements

Import the complete Shopify Product Taxonomy.
Enable asynchronous background processing with Celery.
Improve image-based classification.
Add more advanced search and filtering in the dashboard.