import os
import logging
import magic
import hashlib
import re
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

class SecureFileHandler:
    """Class to securely handle file uploads with enhanced security checks"""
    
    ALLOWED_MIME_TYPES = {
        'application/pdf': ['.pdf'],
        'application/zip': ['.zip'],
        'application/x-zip-compressed': ['.zip'],
        'text/plain': ['.txt'],
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'image/gif': ['.gif']
    }
    
    MAX_FILE_SIZE = 16 * 1024 * 1024
    
    def __init__(self, upload_folder=None):
        """
        Initialize the SecureFileHandler with an upload folder.
        """
        if upload_folder is None:
            logger.error("No upload folder provided.")
            raise ValueError("No upload folder provided.")
        
        # Log the final path to ensure it's correct
        logger.info(f"Upload folder set to: {upload_folder}")
        self.upload_folder = upload_folder
    
    def _check_file_size(self, file_storage):
        file_storage.seek(0, os.SEEK_END)
        size = file_storage.tell()
        file_storage.seek(0)
        
        if size > self.MAX_FILE_SIZE:
            return False, f"File exceeds maximum size of {self.MAX_FILE_SIZE // (1024*1024)}MB"
        return True, "File size is acceptable"
    
    def _verify_mime_type(self, file_path, original_filename):
        try:
            mime = magic.Magic(mime=True)
            detected_mime = mime.from_file(file_path)
            _, ext = os.path.splitext(original_filename)
            ext = ext.lower()
            
            if detected_mime not in self.ALLOWED_MIME_TYPES:
                return False, f"MIME type {detected_mime} is not allowed"
            if ext not in self.ALLOWED_MIME_TYPES.get(detected_mime, []):
                return False, f"File extension does not match content type {detected_mime}"
            return True, "File type verified successfully"
        except Exception as e:
            logger.error(f"Error verifying MIME type: {str(e)}")
            return False, "Error verifying file type"
    
    def _generate_secure_filename(self, original_filename):
        filename = secure_filename(original_filename)
        name, ext = os.path.splitext(filename)
        hash_obj = hashlib.sha256()
        hash_obj.update(f"{name}_{ext}_{os.urandom(8)}".encode('utf-8'))
        hash_str = hash_obj.hexdigest()[:12]
        clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '', name)
        if len(clean_name) > 50:
            clean_name = clean_name[:50]
        secure_name = f"{clean_name}_{hash_str}{ext}"
        return secure_name
    
    def _scan_text_content(self, file_path, mime_type):
        if mime_type != 'text/plain':
            return True, "Not a text file"
            
        suspicious_patterns = [
            # JavaScript risks
            r'<script.*?>',
            r'eval\s*\(',
            r'document\.write\s*\(',
            r'innerHTML\s*=',
            r'setTimeout\s*\(',
            r'setInterval\s*\(',
            r'new\s+Function\s*\(',
            r'fetch\s*\(',
            r'XMLHttpRequest',
            
            # PHP risks
            r'exec\s*\(',
            r'system\s*\(',
            r'shell_exec\s*\(',
            r'passthru\s*\(',
            r'proc_open\s*\(',
            r'popen\s*\(',
            r'curl\s*\(',
            r'file_get_contents\s*\(',
            r'include\s*\(',
            r'require\s*\(',
            r'unserialize\s*\(',
            
            # Python risks
            r'os\s*\.\s*system',
            r'subprocess\s*\.\s*(?:call|Popen|run)',
            r'importlib',
            r'__import__\s*\(',
            r'exec\s*\(',
            r'eval\s*\(',
            r'pickle\s*\.\s*loads',
            
            # SQL injection indicators
            r'UNION\s+SELECT',
            r'SELECT\s+.*\s+FROM',
            r'INSERT\s+INTO',
            r'DELETE\s+FROM',
            r'DROP\s+TABLE',
            r'--\s*$',
            r'/\*.*\*/',
        ]
        
        try:
            with open(file_path, 'r', errors='ignore') as f:
                content = f.read()
                
            for pattern in suspicious_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return False, f"Suspicious pattern detected: {pattern}"
                    
            return True, "Text content scan passed"
        except Exception as e:
            logger.error(f"Error scanning text content: {str(e)}")
            return True, "Error while scanning text content, proceeding with caution"
    
    def _check_for_polyglot_content(self, file_path, detected_mime):
        """
        Check for polyglot files (files that are valid as multiple formats)
        which can be used to bypass security controls
        """
        try:
            # Read the first 8KB of the file for signature checks
            with open(file_path, 'rb') as f:
                header = f.read(8192)
                
            # Check for suspicious header combinations
            suspicious_combinations = [
                # PDF + ZIP polyglot signatures
                (b'%PDF' in header and b'PK\x03\x04' in header),
                # HTML in image files
                (detected_mime.startswith('image/') and (b'<html' in header or b'<script' in header)),
                # Shell script commands in text files
                (detected_mime == 'text/plain' and any(sig in header for sig in 
                    [b'#!/bin/bash', b'#!/bin/sh', b'wget ', b'curl ', b'nc ', b'bash -i'])),
                # Executable code in non-executable files
                (not detected_mime.startswith('application/') and b'MZ' in header[:2])
            ]
            
            if any(suspicious_combinations):
                return False, "Potential polyglot file detected with multiple format signatures"
                
            return True, "File passed polyglot detection check"
            
        except Exception as e:
            logger.error(f"Error in polyglot check: {str(e)}")
            return False, "Error during polyglot file check, rejecting file for safety"
    
    def save_file_securely(self, file_storage):
        if not file_storage:
            return False, "No file provided", None
        
        temp_path = None
        try:
            # 1. Check file size
            size_ok, size_msg = self._check_file_size(file_storage)
            if not size_ok:
                return False, size_msg, None
            
            # 2. Generate secure filename
            original_filename = file_storage.filename
            if not original_filename or original_filename == '':
                return False, "Invalid filename", None
                
            secure_name = self._generate_secure_filename(original_filename)
            
            # 3. Save to temporary location
            temp_path = os.path.join(self.upload_folder, "temp_" + secure_name)
            logger.info(f"Saving file to temp path: {temp_path}")
            file_storage.save(temp_path)
            
            # 4. Verify MIME type matches the extension
            mime_ok, mime_msg = self._verify_mime_type(temp_path, original_filename)
            if not mime_ok:
                os.remove(temp_path)
                return False, mime_msg, None
            
            # 5. Get detected MIME type for additional checks
            mime = magic.Magic(mime=True)
            detected_mime = mime.from_file(temp_path)
            
            # 6. Scan text content if applicable
            if detected_mime == 'text/plain':
                content_ok, content_msg = self._scan_text_content(temp_path, detected_mime)
                if not content_ok:
                    os.remove(temp_path)
                    return False, content_msg, None
            
            # 7. Check for polyglot files (files hiding multiple formats)
            polyglot_ok, polyglot_msg = self._check_for_polyglot_content(temp_path, detected_mime)
            if not polyglot_ok:
                os.remove(temp_path)
                return False, polyglot_msg, None
            
            # 8. Set proper permissions on the file
            try:
                # Make file read-only to prevent modification after upload
                os.chmod(temp_path, 0o440)  # read-only for owner and group
            except Exception as e:
                logger.warning(f"Could not set permissions on file: {str(e)}")
            
            # 9. Move to final location
            final_path = os.path.join(self.upload_folder, secure_name)
            logger.info(f"Moving file to final path: {final_path}")
            os.rename(temp_path, final_path)
            
            # 10. Log successful upload
            logger.info(f"Successfully saved file {original_filename} as {secure_name} with MIME type {detected_mime}")
            return True, "File saved successfully", secure_name
            
        except Exception as e:
            logger.error(f"Error saving file securely: {str(e)}")
            try:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {str(cleanup_error)}")
                
            return False, f"Error processing file: {str(e)}", None