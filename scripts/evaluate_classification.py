import os
import sys
from pypdf import PdfReader

# Setup paths so we can import backend modules from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from services.classification import classify_document

# Load env variables manually to grab TYPESAFE_API_KEY
env_file = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ[key] = val.strip("'\"")

# The evaluation dataset mapping filenames to expected categories
DATASET = [
    {"filename": "invoice_1.pdf", "expected": "invoice"},
    {"filename": "invoice_2.pdf", "expected": "invoice"},
    {"filename": "contract_1.pdf", "expected": "contract"},
    {"filename": "contract_2.pdf", "expected": "contract"},
    {"filename": "hr_form_1.pdf", "expected": "hr_form"},
    {"filename": "hr_form_2.pdf", "expected": "hr_form"},
    {"filename": "academic_1.pdf", "expected": "academic_record"},
    {"filename": "academic_2.pdf", "expected": "academic_record"},
    {"filename": "other_1.pdf", "expected": "other"},
    {"filename": "other_2.pdf", "expected": "other"}
]

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text)

def evaluate():
    print("Evaluating Document Classification System...")
    correct = 0
    total = len(DATASET)
    errors = []
    
    sample_dir = os.path.join(os.path.dirname(__file__), '..', 'sample')
    report_path = os.path.join(os.path.dirname(__file__), '..', 'evaluation_report.md')
    
    with open(report_path, "w", encoding="utf-8") as report:
        report.write("# Document Classification Evaluation Report\n\n")
        report.write("## Dataset Results\n\n")
        report.write("| File | Expected | Predicted | Confidence | Result |\n")
        report.write("|---|---|---|---|---|\n")
        
        for idx, sample in enumerate(DATASET):
            print(f"Evaluating sample {idx + 1}/{total}: {sample['filename']}")
            pdf_path = os.path.join(sample_dir, sample['filename'])
            
            try:
                # Extract text from the physical PDF
                text = extract_text_from_pdf(pdf_path)
                
                # Classify the extracted text
                result = classify_document(text)
                predicted = result.category.value
                conf = result.confidence
                
                is_correct = (predicted == sample["expected"])
                if is_correct:
                    correct += 1
                    status = "✅ Pass"
                else:
                    status = "❌ Fail"
                    errors.append({
                        "file": sample["filename"],
                        "expected": sample["expected"],
                        "predicted": predicted,
                        "confidence": conf
                    })
                    
                report.write(f"| {sample['filename']} | {sample['expected']} | {predicted} | {conf:.2f} | {status} |\n")
            except Exception as e:
                report.write(f"| {sample['filename']} | {sample['expected']} | ERROR | 0.0 | ❌ Error |\n")
                errors.append({
                    "file": sample["filename"],
                    "expected": sample["expected"],
                    "predicted": "ERROR",
                    "error_msg": str(e)
                })
                print(f"Error classifying sample {idx+1}: {e}")
                
        accuracy = (correct / total) * 100
        print(f"\nEvaluation Complete! Accuracy: {accuracy:.1f}%")
        
        report.write(f"\n## Summary\n")
        report.write(f"- **Total PDF Samples:** {total}\n")
        report.write(f"- **Accuracy:** {accuracy:.1f}%\n\n")
        
        report.write("## Major Classification Errors\n")
        if errors:
            for e in errors:
                report.write(f"- **File:** `{e['file']}`\n")
                report.write(f"  - **Expected:** `{e['expected']}` | **Predicted:** `{e['predicted']}`\n")
                if "error_msg" in e:
                    report.write(f"  - **Error:** {e['error_msg']}\n")
        else:
            report.write("None! The classifier achieved perfect accuracy on all sample PDF documents.\n")

    print(f"Report generated at {report_path}")

if __name__ == "__main__":
    evaluate()
