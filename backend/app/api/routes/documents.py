from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.document import DocumentListItem, DocumentResponse, DocumentType
from app.services import document_service

router = APIRouter(prefix="/api/v1", tags=["documents"])


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/documents/process", response_model=DocumentResponse)
async def process_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    return document_service.process_document(
        db=db,
        filename=file.filename,
        document_type=document_type.value,
        content=content,
    )


@router.get("/documents/{document_name}")
def get_document(document_name: str, db: Session = Depends(get_db)):
    return document_service.get_document_by_name(db, document_name)


@router.get("/documents", response_model=list[DocumentListItem])
def list_documents(db: Session = Depends(get_db)):
    return document_service.list_documents(db)
