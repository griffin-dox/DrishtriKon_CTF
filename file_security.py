import os
import logging
import magic
import hashlib
import re
from werkzeug.utils import secure_filename

class SecureFileHandler:
    """Class to securely handle file uploads with enhanced security checks"""
    
    # Allowed MIME types mapped to their extensions
    ALLOWED_MIME_TYPES = {
        'application/pdf': ['.pdf'],
        'application/zip': ['.zip'],
        'application/x-zip-compressed': ['.zip'],
        'text/plain': ['.txt'],
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'image/gif': ['.gif']
    }
    
    # Maximum file size in bytes (16MB)
    MAX_FILE_SIZE = 16 * 1024 * 1024
    
    def __init__(self, upload_folder=None):
        """
        Initialize the SecureFileHandler with an upload folder.
        If upload_folder is not provided, dynamically locate or create an 'Uploads' folder.
        """
        if upload_folder is None:
            # Locate or create the 'Uploads' folder in the current working directory
            current_dir = os.getcwd()
            upload_folder = os.path.join(current_dir, "Uploads")
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder, exist_ok=True)
                logging.info(f"'Uploads' folder created at: {upload_folder}")
            else:
                logging.info(f"'Uploads' folder found at: {upload_folder}")
        
        self.upload_folder = upload_folder
    
    def _check_file_size(self, file_storage):
        """Check if file size is within limits"""
        file_storage.seek(0, os.SEEK_END)
        size = file_storage.tell()
        file_storage.seek(0)  # Reset file pointer
        
        if size > self.MAX_FILE_SIZE:
            return False, f"File exceeds maximum size of {self.MAX_FILE_SIZE // (1024*1024)}MB"
        return True, "File size is acceptable"
    
    def _verify_mime_type(self, file_path, original_filename):
        """Verify the MIME type matches the file extension"""
        try:
            # Get MIME type with python-magic
            mime = magic.Magic(mime=True)
            detected_mime = mime.from_file(file_path)
            
            # Get the file extension
            _, ext = os.path.splitext(original_filename)
            ext = ext.lower()
            
            # Check if detected MIME type is allowed
            if detected_mime not in self.ALLOWED_MIME_TYPES:
                return False, f"MIME type {detected_mime} is not allowed"
                
            # Check if extension matches the MIME type
            if ext not in self.ALLOWED_MIME_TYPES.get(detected_mime, []):
                return False, f"File extension does not match content type {detected_mime}"
                
            return True, "File type verified successfully"
        except Exception as e:
            logging.error(f"Error verifying MIME type: {str(e)}")
            return False, "Error verifying file type"
    
    def _generate_secure_filename(self, original_filename):
        """Generate a secure filename with additional safeguards"""
        # First use werkzeug's secure_filename
        filename = secure_filename(original_filename)
        
        # Get file extension
        name, ext = os.path.splitext(filename)
        
        # Add hash to make it unique - prevents directory traversal and name collisions
        hash_obj = hashlib.sha256()
        hash_obj.update(f"{name}_{ext}_{os.urandom(8)}".encode('utf-8'))
        hash_str = hash_obj.hexdigest()[:12]
        
        # Clean name further (just to be extra safe)
        clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '', name)
        
        # Truncate name if too long
        if len(clean_name) > 50:
            clean_name = clean_name[:50]
            
        # Build final filename
        secure_name = f"{clean_name}_{hash_str}{ext}"
        
        return secure_name
    
    def _scan_text_content(self, file_path, mime_type):
        """Scan text files for potentially malicious content"""
        if mime_type != 'text/plain':
            return True, "Not a text file"
            
        suspicious_patterns = [
            r'<script.*?>',  # Basic JavaScript tags
            r'eval\s*\(',    # JavaScript eval()
            r'exec\s*\(',    # Various code execution patterns
            r'system\s*\(',
            r'shell_exec\s*\(',
            r'passthru\s*\(',
            r'proc_open\s*\(',
            r'popen\s*\(',
            r'curl\s*\(',    # Network access
            r'file_get_contents\s*\(',  # File operations
            r'include\s*\(',
            r'require\s*\(',
        ]
        
        try:
            with open(file_path, 'r', errors='ignore') as f:
                content = f.read()
                
            for pattern in suspicious_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return False, f"Suspicious pattern detected: {pattern}"
                    
            return True, "Text content scan passed"
        except Exception as e:
            logging.error(f"Error scanning text content: {str(e)}")
            return True, "Error while scanning text content, proceeding with caution"
    
    def save_file_securely(self, file_storage):
        """
        Save a file with security checks
        Returns a tuple: (success, message, saved_filename_or_none)
        """
        if not file_storage:
            return False, "No file provided", None
            
        try:
            # Check file size
            size_ok, size_msg = self._check_file_size(file_storage)
            if not size_ok:
                return False, size_msg, None
                
            # Generate a secure filename
            original_filename = file_storage.filename
            secure_name = self._generate_secure_filename(original_filename)
            
            # Save the file to a temporary location
            temp_path = os.path.join(self.upload_folder, "temp_" + secure_name)
            file_storage.save(temp_path)
            
            # Verify MIME type
            mime_ok, mime_msg = self._verify_mime_type(temp_path, original_filename)
            if not mime_ok:
                os.remove(temp_path)  # Clean up
                return False, mime_msg, None
                
            # Get MIME type for text scanning
            mime = magic.Magic(mime=True)
            detected_mime = mime.from_file(temp_path)
            
            # Scan content if it's a text file
            if detected_mime == 'text/plain':
                content_ok, content_msg = self._scan_text_content(temp_path, detected_mime)
                if not content_ok:
                    os.remove(temp_path)  # Clean up
                    return False, content_msg, None
            
            # Move to final location
            final_path = os.path.join(self.upload_folder, secure_name)
            os.rename(temp_path, final_path)
            
            return True, "File saved successfully", secure_name
            
        except Exception as e:
            logging.error(f"Error saving file securely: {str(e)}")
            # Attempt to clean up
            try:
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass
            return False, f"Error processing file: {str(e)}", None