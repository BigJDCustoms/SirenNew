
from flask import Flask, render_template, request, send_file
import os
import zipfile
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict

app = Flask(__name__)

def get_top_level_group(base_folder, file_path):
    rel_path = os.path.relpath(file_path, base_folder)
    parts = rel_path.split(os.sep)
    return parts[0] if parts else ""

def extract_siren_data_from_all_folders(base_folder):
    entries = []
    for root, dirs, files in os.walk(base_folder):
        for file in files:
            if file.lower() == "carvariations.meta":
                file_path = os.path.join(root, file)
                try:
                    tree = ET.parse(file_path)
                    root_element = tree.getroot()
                    for item in root_element.iter():
                        model = None
                        siren = None
                        for elem in item.iter():
                            if elem.tag == "modelName":
                                model = (elem.text or "").strip()
                            if elem.tag == "sirenSettings" and "value" in elem.attrib:
                                siren = elem.attrib["value"]
                        if model and siren and siren.strip() != "0":
                            group = get_top_level_group(base_folder, file_path)
                            entries.append((model, siren, group))
                except ET.ParseError:
                    continue
    return entries

def find_conflicts(data):
    siren_map = defaultdict(list)
    for model, siren, group in data:
        siren_map[siren].append((model, group))
    conflicts = {
        sid: models for sid, models in siren_map.items()
        if len(set(group for _, group in models)) > 1
    }
    return conflicts

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/scan", methods=["POST"])
def scan():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, "uploaded.zip")
        file.save(zip_path)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        results = extract_siren_data_from_all_folders(temp_dir)
        conflicts = find_conflicts(results)

        output_path = os.path.join(temp_dir, "siren_conflicts_results.txt")
        with open(output_path, "w") as f:
            if not results:
                f.write("No sirenSettings found.\n")
            else:
                for model, siren, group in results:
                    f.write(f"{model}: {siren} (in {group})\n")
                if conflicts:
                    f.write("\n--- Conflicts Detected ---\n")
                    for sid, models in conflicts.items():
                        f.write(f"Siren ID {sid} used by:\n")
                        for m, g in models:
                            f.write(f"  - {m} (in {g})\n")
                        f.write("\n")

        return send_file(output_path, as_attachment=True, download_name="siren_conflicts_results.txt")

if __name__ == "__main__":
    app.run(debug=True)
