"""
Forms for Public Chatbot Admin - Bulk Document Upload
"""
from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from .document_processor import DocumentProcessor


class MultipleFileInput(forms.ClearableFileInput):
    """Custom widget for multiple file uploads"""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Custom field for multiple file uploads"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


class BulkDocumentUploadForm(forms.Form):
    """
    Form for bulk document upload in Django admin
    """
    
    # File upload field
    files = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'multiple': True,
            'accept': ','.join(DocumentProcessor.get_supported_formats()),
            'class': 'form-control-file'
        }),
        help_text=f"""
        Upload multiple documents at once. Supported formats: {', '.join(DocumentProcessor.get_supported_formats())}<br>
        Maximum file size: 50MB per file, 200MB total batch size.
        """
    )
    
    # Category selection
    category = forms.CharField(
        max_length=50,
        initial='general',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., documentation, faq, technical'
        }),
        help_text="Category for all uploaded documents (can be changed individually later)"
    )
    
    # Auto-approval options
    auto_approve = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Automatically approve documents for public use (requires admin privileges)"
    )
    
    auto_security_review = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Mark documents as security reviewed (requires admin privileges)"
    )
    
    # Processing options
    auto_sync = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Automatically sync approved documents to ChromaDB after upload"
    )
    
    # Quality settings
    min_quality_score = forms.IntegerField(
        initial=30,
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '10'
        }),
        help_text="Minimum quality score (0-100) to accept documents"
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Check available format processors
        dependencies = DocumentProcessor.check_dependencies()
        missing_deps = [fmt for fmt, available in dependencies.items() if not available]
        
        if missing_deps:
            self.fields['files'].help_text += f"""<br>
            <strong>Note:</strong> Some formats may have limited support due to missing dependencies: {', '.join(missing_deps)}
            """
    
    def clean_files(self):
        """Validate uploaded files"""
        files = self.cleaned_data.get('files', [])
        
        # Handle case where files is not a list (single file or None)
        if not isinstance(files, list):
            files = [files] if files else []
        
        # Filter out None values
        files = [f for f in files if f is not None]
        
        if not files:
            raise ValidationError("Please select at least one file to upload.")
        
        if len(files) > 50:
            raise ValidationError("Maximum 50 files allowed per upload.")
        
        # Check total size
        total_size = sum(f.size for f in files if hasattr(f, 'size'))
        if total_size > DocumentProcessor.MAX_TOTAL_SIZE:
            size_mb = total_size / 1024 / 1024
            limit_mb = DocumentProcessor.MAX_TOTAL_SIZE / 1024 / 1024
            raise ValidationError(f"Total upload size ({size_mb:.1f}MB) exceeds limit ({limit_mb}MB)")
        
        # Validate individual files
        supported_formats = DocumentProcessor.get_supported_formats()
        for file_obj in files:
            # Check file extension
            if hasattr(file_obj, 'name') and file_obj.name:
                from pathlib import Path
                ext = Path(file_obj.name).suffix.lower()
                if ext not in supported_formats:
                    raise ValidationError(f"Unsupported file format: {ext} in file {file_obj.name}")
            
            # Check individual file size
            if hasattr(file_obj, 'size') and file_obj.size > DocumentProcessor.MAX_FILE_SIZE:
                size_mb = file_obj.size / 1024 / 1024
                limit_mb = DocumentProcessor.MAX_FILE_SIZE / 1024 / 1024
                raise ValidationError(f"File {file_obj.name} ({size_mb:.1f}MB) exceeds limit ({limit_mb}MB)")
        
        return files
    
    def clean_category(self):
        """Validate category"""
        category = self.cleaned_data['category'].strip().lower()
        
        if not category:
            return 'general'
        
        # Sanitize category name
        import re
        category = re.sub(r'[^a-z0-9_-]', '', category)
        if not category:
            return 'general'
        
        return category[:50]  # Limit length
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        
        # Check permissions for auto-approval
        auto_approve = cleaned_data.get('auto_approve')
        auto_security_review = cleaned_data.get('auto_security_review')
        
        if (auto_approve or auto_security_review) and self.user:
            if not (self.user.is_superuser or self.user.is_staff):
                raise ValidationError("Auto-approval requires admin privileges.")
        
        return cleaned_data


class DocumentProcessingForm(forms.Form):
    """
    Form for processing already uploaded documents
    """
    
    # Processing options
    force_reprocess = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Force reprocessing of documents that were already processed"
    )
    
    update_metadata = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Update document metadata (title, tags, quality score)"
    )
    
    # Approval workflow
    approve_processed = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Automatically approve successfully processed documents"
    )
    
    sync_after_processing = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Sync to ChromaDB after processing (only approved documents)"
    )


class BatchActionForm(forms.Form):
    """
    Form for batch actions on existing documents
    """
    
    ACTION_CHOICES = [
        ('approve', 'Approve selected documents'),
        ('sync', 'Sync to ChromaDB immediately'),
        ('reprocess', 'Reprocess document content'),
        ('update_quality', 'Recalculate quality scores'),
        ('extract_metadata', 'Re-extract titles and tags'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    confirm = forms.BooleanField(
        required=True,
        help_text="Confirm you want to perform this batch action"
    )
    
    # Action-specific options
    force_update = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Force update even if already processed (for sync and reprocess)"
    )


class DocumentImportForm(forms.Form):
    """
    Form for importing documents from various sources
    """
    
    SOURCE_CHOICES = [
        ('file_upload', 'Upload Files'),
        ('url_list', 'Import from URLs'),
        ('directory', 'Import from Directory Path'),
        ('csv_metadata', 'Import with CSV Metadata'),
    ]
    
    import_source = forms.ChoiceField(
        choices=SOURCE_CHOICES,
        widget=forms.RadioSelect,
        initial='file_upload'
    )
    
    # File upload (default)
    files = MultipleFileField(
        required=False
    )
    
    # URL import
    url_list = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 10,
            'placeholder': 'Enter URLs, one per line:\nhttps://example.com/doc1.pdf\nhttps://example.com/doc2.html'
        }),
        required=False,
        help_text="Enter URLs to documents, one per line"
    )
    
    # Directory import (for local files)
    directory_path = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '/path/to/documents/'
        }),
        help_text="Local directory path containing documents to import"
    )
    
    # CSV metadata import
    metadata_csv = forms.FileField(
        required=False,
        help_text="CSV file with document metadata (filename, title, category, tags)"
    )
    
    # Common settings
    default_category = forms.CharField(
        max_length=50,
        initial='imported',
        required=False
    )
    
    auto_approve = forms.BooleanField(required=False)
    auto_sync = forms.BooleanField(required=False, initial=True)
    
    def clean(self):
        cleaned_data = super().clean()
        import_source = cleaned_data.get('import_source')
        
        # Validate based on selected source
        if import_source == 'file_upload':
            if not cleaned_data.get('files'):
                raise ValidationError("Please select files to upload.")
                
        elif import_source == 'url_list':
            if not cleaned_data.get('url_list'):
                raise ValidationError("Please provide URLs to import.")
                
        elif import_source == 'directory':
            if not cleaned_data.get('directory_path'):
                raise ValidationError("Please provide directory path.")
                
        elif import_source == 'csv_metadata':
            if not cleaned_data.get('metadata_csv'):
                raise ValidationError("Please provide CSV metadata file.")
        
        return cleaned_data