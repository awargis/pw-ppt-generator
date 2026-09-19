import re
from typing import Optional

def normalize_subject(value: Optional[str], known_subjects: list[str]) -> Optional[str]:
    """
    Takes any detected header text (e.g., 'SECTION-II (CHEMISTRY)') and 
    extracts the clean subject name based on the exam type.
    """
    if not value: return None
    
    # Clean the string: lowercase and keep only letters
    clean_value = re.sub(r"[^a-z\s]", " ", str(value).lower()).strip()
    
    # Common aliases
    aliases = {
        "math": "Mathematics",
        "maths": "Mathematics",
        "phy": "Physics",
        "chem": "Chemistry",
        "bot": "Botany",
        "zoo": "Zoology"
    }
    
    for word in clean_value.split():
        if word in aliases and aliases[word] in known_subjects:
            return aliases[word]

    # Direct match
    for subject in known_subjects:
        if subject.lower() in clean_value: 
            return subject
            
    return None
