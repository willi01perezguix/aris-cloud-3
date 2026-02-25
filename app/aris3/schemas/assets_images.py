from pydantic import BaseModel


class ImageUploadResponse(BaseModel):
    image_asset_id: str
    image_url: str
    image_thumb_url: str
    image_source: str
    image_updated_at: str
