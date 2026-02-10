import os
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger("uvicorn.error")

class TemplateService:
    BLUEPRINT_DIR = Path("app/blueprints")

    @staticmethod
    def list_templates(limit: int = 20, offset: int = 0) -> tuple[List[Dict[str, str]], int]:
        """
        Scans all files in BLUEPRINT_DIR and returns paginated metadata.
        """
        templates = []
        if not TemplateService.BLUEPRINT_DIR.exists():
            return [], 0

        for root, _, files in os.walk(TemplateService.BLUEPRINT_DIR):
            for file in files:
                if file.endswith((".yaml", ".yml")):
                    full_path = Path(root) / file
                    metadata = TemplateService._parse_metadata(full_path)
                    
                    # Compute relative path for ID/Name usage
                    rel_path = full_path.relative_to(TemplateService.BLUEPRINT_DIR)
                    name_id = str(rel_path).replace("\\", "/") # normalize for web
                    
                    templates.append({
                        "id": name_id,
                        "title": metadata.get("Title", name_id),
                        "description": metadata.get("Description", "No description provided"),
                        "category": metadata.get("Category", "Uncategorized"),
                        "author": metadata.get("Author", "Unknown")
                    })
        
        # Sort by title
        sorted_templates = sorted(templates, key=lambda x: x["title"].lower())
        total_count = len(sorted_templates)
        
        return sorted_templates[offset : offset + limit], total_count

    @staticmethod
    def get_template_content(name_id: str) -> Optional[str]:
        """
        Returns the raw content of a template by its relative ID.
        """
        try:
            # Security check to prevent path traversal
            safe_path = (TemplateService.BLUEPRINT_DIR / name_id).resolve()
            if not str(safe_path).startswith(str(TemplateService.BLUEPRINT_DIR.resolve())):
                logger.warning(f"Attempted path traversal: {name_id}")
                return None
            
            if not safe_path.exists():
                return None
                
            return safe_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Error reading template {name_id}: {e}")
            return None

    @staticmethod
    def _parse_metadata(path: Path) -> Dict[str, str]:
        """
        Reads the first few lines looking for # Key: Value
        """
        metadata = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                for match in range(10): # Only check first 10 lines
                    line = f.readline()
                    if not line: break
                    line = line.strip()
                    if line.startswith("#"):
                        # remove leading # and split
                        parts = line[1:].split(":", 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = parts[1].strip()
                            metadata[key] = value
        except Exception as e:
            logger.error(f"Failed to parse metadata for {path}: {e}")
        return metadata

    @staticmethod
    def save_template(name_id: str, content: str) -> bool:
        """
        Creates or updates a template file.
        """
        try:
             # Basic validation
            if ".." in name_id or name_id.startswith("/"):
                raise ValueError("Invalid filename")
            
            # Ensure extension
            if not name_id.endswith(('.yml', '.yaml')):
                name_id += '.yml'
                
            safe_path = (TemplateService.BLUEPRINT_DIR / name_id).resolve()
            
            # Ensure it's within the blueprint dir
            if not str(safe_path).startswith(str(TemplateService.BLUEPRINT_DIR.resolve())):
                 raise ValueError("Path traversal attempt")
            
            # Ensure parent directories exist (if subfolders used)
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Error saving template {name_id}: {e}")
            return False

    @staticmethod
    def delete_template(name_id: str) -> bool:
        """
        Deletes a template file.
        """
        try:
            safe_path = (TemplateService.BLUEPRINT_DIR / name_id).resolve()
            if not str(safe_path).startswith(str(TemplateService.BLUEPRINT_DIR.resolve())):
                return False
            
            if safe_path.exists() and safe_path.is_file():
                safe_path.unlink()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting template {name_id}: {e}")
            return False
