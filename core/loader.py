import os
import json

class DataLoader:
    def __init__(self, data_path="data"):
        self.data_path = data_path

    def load_json(self):
        all_data = []
        
        if not os.path.exists(self.data_path):
            return all_data

        for file in os.listdir(self.data_path):
            if file.endswith(".json"):
                path = os.path.join(self.data_path, file)
                
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        all_data.extend(data)
                    else:
                        all_data.append(data)
                        
        return all_data

    def load_text(self):
        documents = []
        
        if not os.path.exists(self.data_path):
            return documents

        for file in os.listdir(self.data_path):
            if file.endswith(".md"):
                path = os.path.join(self.data_path, file)
                
                with open(path, encoding="utf-8") as f:
                    documents.append({
                        "file": file,
                        "content": f.read()
                    })
                    
        return documents