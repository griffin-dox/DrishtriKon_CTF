"""
Custom form validators for secure file uploads.

These validators provide strict client and server-side validation
for file uploads with focus on security.
"""

from wtforms.validators import ValidationError, StopValidation
import mimetypes


class SecureFileRequired:
    """
    Validates that a file field contains a file.
    More strict than FileRequired.
    """
    
    def __init__(self, message=None):
        self.message = message or "File is required."
    
    def __call__(self, form, field):
        if not field.data or not hasattr(field.data, 'filename'):
            raise StopValidation(self.message)
        
        if not field.data.filename:
            raise StopValidation(self.message)


class SecureFileAllowed:
    """
    Validates file extensions and MIME types.
    Stricter than standard FileAllowed validator.
    """
    
    def __init__(self, extensions, mime_types=None, message=None):
        """
        Initialize validator.
        
        Args:
            extensions: List of allowed extensions (with or without dots)
            mime_types: List of allowed MIME types (optional but recommended)
            message: Custom error message
        """
        # Normalize extensions to include dots
        self.extensions = [ext if ext.startswith('.') else f'.{ext}' 
                          for ext in extensions]
        self.mime_types = mime_types
        self.message = message or f"Only {', '.join(self.extensions)} files are allowed."
    
    def __call__(self, form, field):
        if not field.data:
            return
        
        filename = field.data.filename
        
        # Check if filename has an extension
        if '.' not in filename:
            raise ValidationError("File must have an extension.")
        
        # Get file extension
        ext = '.' + filename.rsplit('.', 1)[1].lower()
        
        # Validate extension
        if ext not in self.extensions:
            raise ValidationError(
                f"File type '{ext}' not allowed. Allowed types: {', '.join(self.extensions)}"
            )
        
        # Validate MIME type if provided
        if self.mime_types and hasattr(field.data, 'content_type'):
            content_type = field.data.content_type
            
            if content_type not in self.mime_types:
                raise ValidationError(
                    f"File content type '{content_type}' not allowed."
                )


class FileSize:
    """
    Validates file size.
    """
    
    def __init__(self, max_size, message=None):
        """
        Initialize validator.
        
        Args:
            max_size: Maximum size in bytes
            message: Custom error message
        """
        self.max_size = max_size
        if message:
            self.message = message
        else:
            max_mb = max_size / (1024 * 1024)
            self.message = f"File size must not exceed {max_mb:.1f}MB"
    
    def __call__(self, form, field):
        if not field.data:
            return
        
        # Get file size
        field.data.seek(0, 2)  # Seek to end
        size = field.data.tell()
        field.data.seek(0)  # Reset to beginning
        
        if size > self.max_size:
            current_mb = size / (1024 * 1024)
            raise ValidationError(
                f"File size ({current_mb:.2f}MB) exceeds maximum allowed ({self.max_size / (1024 * 1024):.1f}MB)"
            )


class SafeFilename:
    """
    Validates that filename doesn't contain dangerous characters.
    """
    
    DANGEROUS_CHARS = ['..', '/', '\\', '<', '>', ':', '"', '|', '?', '*', '\x00']
    
    def __init__(self, message=None):
        self.message = message or "Filename contains invalid characters."
    
    def __call__(self, form, field):
        if not field.data:
            return
        
        filename = field.data.filename
        
        # Check for dangerous character sequences
        for char in self.DANGEROUS_CHARS:
            if char in filename:
                raise ValidationError(
                    f"Filename contains invalid character: '{char}'"
                )
        
        # Check filename length
        if len(filename) > 255:
            raise ValidationError("Filename is too long (max 255 characters)")
        
        # Check for hidden files (Unix-style)
        if filename.startswith('.'):
            raise ValidationError("Hidden files are not allowed")


class ImageDimensions:
    """
    Validates image dimensions (requires PIL/Pillow).
    """
    
    def __init__(self, max_width=None, max_height=None, min_width=None, min_height=None, message=None):
        """
        Initialize validator.
        
        Args:
            max_width: Maximum width in pixels
            max_height: Maximum height in pixels
            min_width: Minimum width in pixels
            min_height: Minimum height in pixels
            message: Custom error message
        """
        self.max_width = max_width
        self.max_height = max_height
        self.min_width = min_width
        self.min_height = min_height
        self.message = message
    
    def __call__(self, form, field):
        if not field.data:
            return
        
        try:
            from PIL import Image
        except ImportError:
            # If PIL not available, skip this validation
            return
        
        try:
            # Save current position
            field.data.seek(0)
            
            # Open image
            img = Image.open(field.data)
            width, height = img.size
            
            # Reset file position
            field.data.seek(0)
            
            # Validate dimensions
            if self.max_width and width > self.max_width:
                raise ValidationError(
                    f"Image width ({width}px) exceeds maximum ({self.max_width}px)"
                )
            
            if self.max_height and height > self.max_height:
                raise ValidationError(
                    f"Image height ({height}px) exceeds maximum ({self.max_height}px)"
                )
            
            if self.min_width and width < self.min_width:
                raise ValidationError(
                    f"Image width ({width}px) is below minimum ({self.min_width}px)"
                )
            
            if self.min_height and height < self.min_height:
                raise ValidationError(
                    f"Image height ({height}px) is below minimum ({self.min_height}px)"
                )
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError("Invalid image file")
