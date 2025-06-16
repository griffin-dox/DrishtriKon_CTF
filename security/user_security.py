import re
import logging
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)

# Password complexity requirements
PASSWORD_MIN_LENGTH = 8
PASSWORD_COMPLEXITY_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9!@#$%^&*(),.?\":{}|<>]).*$"
COMMON_PASSWORDS = [
    "password", "12345678", "qwerty", "123456", "123456789", 
    "12345", "1234", "111111", "1234567", "dragon", 
    "123123", "baseball", "abc123", "football", "monkey", 
    "letmein", "696969", "shadow", "master", "666666", 
    "qwertyuiop", "123321", "mustang", "1234567890", "michael", 
    "654321", "superman", "1qaz2wsx", "7777777", "fuckyou",
    "admin", "admin123", "administrator", "root", "adminadmin"
]

def validate_password_strength(password):
    """
    Validate password strength against security requirements.
    Returns a tuple of (valid, message).
    """
    # Check length
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
    
    # Check for common passwords
    if password.lower() in COMMON_PASSWORDS:
        return False, "Password is too common and easily guessable"
        
    # Check pattern with regex
    if not re.match(PASSWORD_COMPLEXITY_REGEX, password):
        return False, "Password must contain lowercase, uppercase, and either numbers or special characters"
        
    return True, "Password meets security requirements"

def secure_hash_password(password):
    """Generate a secure password hash using PBKDF2"""
    # Default method is pbkdf2:sha256 with salt
    return generate_password_hash(password)
    
def verify_password_hash(password_hash, password):
    """Verify a password against its hash"""
    if not password_hash:
        return False
        
    return check_password_hash(password_hash, password)

def calc_password_strength_score(password):
    """Calculate a password strength score from 0-100"""
    if not password:
        return 0
        
    score = 0
    
    # Length contribution (up to 40 points)
    length_score = min(len(password) * 4, 40)
    score += length_score
    
    # Character variety (up to 40 points)
    has_lower = bool(re.search(r'[a-z]', password))
    has_upper = bool(re.search(r'[A-Z]', password))
    has_digit = bool(re.search(r'[0-9]', password))
    has_special = bool(re.search(r'[^a-zA-Z0-9]', password))
    
    variety_score = (has_lower * 10) + (has_upper * 10) + (has_digit * 10) + (has_special * 10)
    score += variety_score
    
    # Pattern penalties
    # Penalize sequential characters
    sequential_matches = max(
        len(re.findall(r'abcdefghijklmnopqrstuvwxyz', password.lower())),
        len(re.findall(r'01234567890', password)),
        len(re.findall(r'qwertyuiop|asdfghjkl|zxcvbnm', password.lower()))
    )
    score -= sequential_matches * 5
    
    # Penalize repeated characters
    repeated_chars = len(re.findall(r'(.)\1{2,}', password))
    score -= repeated_chars * 5
    
    # Common password penalty
    if password.lower() in COMMON_PASSWORDS:
        score -= 40
    
    # Ensure score is between 0-100
    return max(0, min(score, 100))

def get_password_strength_label(score):
    """Convert numerical password strength to a label"""
    if score < 20:
        return "Very Weak"
    elif score < 40:
        return "Weak"
    elif score < 60:
        return "Moderate"
    elif score < 80:
        return "Strong"
    else:
        return "Very Strong"

class PasswordBreachDetector:
    """Simple class to check if a password has been previously breached"""
    
    @staticmethod
    def is_password_breached(password):
        """
        Check if password appears in a database of known breached passwords.
        In a real application, this would use an API like HaveIBeenPwned
        or a local database of breached passwords.
        """
        # TODO: Integrate with HaveIBeenPwned or similar API for real password breach checks.
        # Example implementation - replace with real breach checking logic
        return password.lower() in COMMON_PASSWORDS
    
    @staticmethod
    def check_password_leak(password):
        """
        More detailed password breach check returning severity level.
        0 = Not breached
        1 = Low severity (found in minor breaches)
        2 = Medium severity (found in several breaches)
        3 = High severity (found in major breaches)
        """
        # TODO: Integrate with HaveIBeenPwned or similar API for real password breach checks.
        # Example implementation - replace with real breach checking logic
        if password.lower() in COMMON_PASSWORDS:
            return 3
        elif len(password) < 8:
            return 2
        elif not re.match(PASSWORD_COMPLEXITY_REGEX, password):
            return 1
        return 0