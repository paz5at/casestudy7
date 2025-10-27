from flask import Flask, request, jsonify, render_template
from azure.storage.blob import BlobServiceClient, ContentSettings
from datetime import datetime
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# load environment variables
load_dotenv()

# configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
STORAGE_ACCOUNT_URL = os.getenv('STORAGE_ACCOUNT_URL', 'https://lanvyp.blob.core.windows.net')
CONTAINER_NAME = os.getenv('IMAGES_CONTAINER', 'lanternfly-images')
MAX_FILE_SIZE = 10 * 1024 * 1024  

# initialize blob service client
bsc = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
cc = bsc.get_container_client(CONTAINER_NAME)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

def is_allowed_file(filename):
    """Check if file has an allowed image extension"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_blob_name(original_filename):
    """Generate timestamped blob name"""
    timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%S')
    safe_filename = secure_filename(original_filename)
    return f"{timestamp}-{safe_filename}"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/v1/upload", methods=["POST"])
def upload():
    try:
        # check if file is present
        if 'file' not in request.files:
            return jsonify(ok=False, error="No file provided"), 400
        
        f = request.files['file']
        
        # check if filename is empty
        if f.filename == '':
            return jsonify(ok=False, error="No file selected"), 400
        
        # validate file type
        if not is_allowed_file(f.filename):
            return jsonify(ok=False, error="Invalid file type. Only image files allowed."), 400
        
        # check content type
        if not f.content_type or not f.content_type.startswith('image/'):
            return jsonify(ok=False, error="File must be an image"), 400
        
        # generate blob name with timestamp
        blob_name = generate_blob_name(f.filename)
        
        # upload to Azure Blob Storage
        blob_client = cc.get_blob_client(blob_name)
        
        # read file content
        file_content = f.read()
        
        # upload blob with content type
        blob_client.upload_blob(
            file_content,
            overwrite=True,
            content_settings=ContentSettings(content_type=f.content_type)
        )
        
        # generate public URL
        blob_url = f"{cc.url}/{blob_name}"
        
        app.logger.info(f"Successfully uploaded: {blob_name}")
        return jsonify(ok=True, url=blob_url), 200
        
    except Exception as e:
        app.logger.error(f"Upload error: {str(e)}")
        return jsonify(ok=False, error=str(e)), 500

@app.route("/api/v1/gallery", methods=["GET"])
def gallery():
    try:
        # list all blobs in the container
        blob_list = cc.list_blobs()
        
        # generate URLs for all blobs
        gallery_urls = [f"{cc.url}/{blob.name}" for blob in blob_list]
        
        # sort by name 
        gallery_urls.sort(reverse=True)
        
        return jsonify(ok=True, gallery=gallery_urls), 200
        
    except Exception as e:
        app.logger.error(f"Gallery error: {str(e)}")
        return jsonify(ok=False, error=str(e)), 500

@app.get("/api/v1/health")
def health():
    """Health check endpoint. Checks connection to Azure Blob Storage."""
    if cc is None:
        return jsonify(
            status="UNHEALTHY", message="Storage client failed to initialize"
        ), 503
    try:
        # Simple check: try to get container properties (cheap operation)
        cc.get_container_properties()
        return jsonify(status="OK", message="Azure Storage connection successful"), 200
    except Exception as e:
        return jsonify(
            status="DEGRADED", message=f"Storage connection failed: {e}"
        ), 503

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)