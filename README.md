# OCR Application

## Overview

The OCR Application is a Python-based tool designed to extract text from PDF documents using Optical Character Recognition (OCR). The application leverages Google Drive API for OCR processing and PyQt5 for the graphical user interface. It allows users to open PDF files, perform OCR on individual pages or the entire document, and save the extracted text.

## Features

- **PDF Handling**: Open and view PDF documents.
- **OCR Processing**: Perform OCR on individual pages or the entire document.
- **Text Editing**: Edit and save the extracted text.
- **Project Management**: Save and load OCR projects.
- **Font Customization**: Adjust font size and type for the extracted text.
- **Status Bar**: Displays project information and status.

## Installation

### Prerequisites

- Python 3.6 or higher
- PyQt5
- PyMuPDF (fitz)
- Google API Client
- Google Auth Library

### Steps

1. **Clone the Repository**

   ```bash
   git clone https://github.com/sujithrex/ocr-application.git
   cd ocr-application
   ```

2. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up Google API Credentials**

   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Create a new project.
   - Enable the Google Drive API.
   - Create credentials and download the `client_secret.json` file.
   - Place the `client_secret.json` file in the root directory of the project.

4. **Run the Application**

   ```bash
   python main.py
   ```

## Usage

### Opening a PDF

1. Click on `File` > `Open` to select a PDF file.
2. The PDF will be loaded, and you can view the pages in the middle section.

### Performing OCR

- **Current Page OCR**: Click on `Operations` > `Current Page OCR` to perform OCR on the currently displayed page.
- **Full OCR**: Click on `Operations` > `Full OCR` to perform OCR on the entire document.

### Saving and Loading Projects

- **Save Project**: Click on `File` > `Save Project` to save the current project.
- **Save Project As**: Click on `File` > `Save As` to save the project with a new name.
- **Open Project**: Click on `File` > `Open` to load a previously saved project.

### Saving Results

- **Save Results**: Click on `Operations` > `Save Results` to save the extracted text to a text file.

### Font Customization

- **Increase Font Size**: Click on `Font` > `Increase Font Size`.
- **Decrease Font Size**: Click on `Font` > `Decrease Font Size`.
- **Choose Font**: Click on `Font` > `Choose Font` to select a different font.

## Developer Information

- **Developer**: Sujith S
- **Website**: [rexmi.in](https://rexmi.in)
- **GitHub**: [sujithrex](https://github.com/sujithrex)

## License

This project is open-source and available under the [MIT License](LICENSE).

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any bugs or feature requests.

## Acknowledgments

- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/)
- [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/)
- [Google API Client](https://github.com/googleapis/google-api-python-client)
- [Google Auth Library](https://github.com/googleapis/google-auth-library-python)

---

For any questions or support, please contact [Sujith S](mailto:sujith@rexmi.in).
