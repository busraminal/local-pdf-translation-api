import os
import time
import uuid
from typing import Literal

import requests
from azure.storage.blob import (
    BlobServiceClient,
    ContainerSasPermissions,
    generate_container_sas,
)

from azure_config import (
    AZURE_TRANSLATOR_ENDPOINT,
    AZURE_TRANSLATOR_KEY,
    AZURE_TRANSLATOR_REGION,
    AZURE_STORAGE_CONNECTION_STRING,
    SOURCE_CONTAINER,
    TARGET_CONTAINER,
)


blob_service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)


def _ensure_containers() -> None:
    blob_service.get_blob_container_client(SOURCE_CONTAINER).create_if_not_exists()
    blob_service.get_blob_container_client(TARGET_CONTAINER).create_if_not_exists()


def upload_pdf_to_source(local_path: str) -> str:
    """
    Verilen local PDF dosyasını source container'a yükler ve
    container seviyesinde read+list izinli SAS URL döner.
    """
    _ensure_containers()
    container = blob_service.get_blob_container_client(SOURCE_CONTAINER)

    blob_name = f"{uuid.uuid4()}-{os.path.basename(local_path)}"
    blob_client = container.get_blob_client(blob_name)

    with open(local_path, "rb") as f:
        blob_client.upload_blob(f, overwrite=True)

    sas = generate_container_sas(
        account_name=blob_service.account_name,
        container_name=container.container_name,
        account_key=blob_service.credential.account_key,  # type: ignore[attr-defined]
        permission=ContainerSasPermissions(read=True, list=True),
        expiry=time.time() + 3600,
    )
    return f"{container.url}?{sas}"


def target_container_sas() -> str:
    """
    Target container için read+write+list izinli SAS URL üretir.
    Azure, çevrilmiş PDF'leri buraya yazar.
    """
    _ensure_containers()
    container = blob_service.get_blob_container_client(TARGET_CONTAINER)

    sas = generate_container_sas(
        account_name=blob_service.account_name,
        container_name=container.container_name,
        account_key=blob_service.credential.account_key,  # type: ignore[attr-defined]
        permission=ContainerSasPermissions(
            read=True, write=True, list=True, create=True, add=True
        ),
        expiry=time.time() + 3600,
    )
    return f"{container.url}?{sas}"


def start_batch_translation(
    source_sas: str,
    target_sas: str,
    from_lang: Literal["tr", "en"],
    to_lang: Literal["tr", "en"],
) -> str:
    """
    Azure Document Translation batch job başlatır ve jobId döner.
    """
    url = f"{AZURE_TRANSLATOR_ENDPOINT}/translator/document/batches?api-version=2024-05-01"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_TRANSLATOR_KEY,
        "Ocp-Apim-Subscription-Region": AZURE_TRANSLATOR_REGION,
        "Content-Type": "application/json",
    }
    body = {
        "inputs": [
            {
                "source": {"sourceUrl": source_sas, "language": from_lang},
                "targets": [{"targetUrl": target_sas, "language": to_lang}],
            }
        ]
    }

    resp = requests.post(url, json=body, headers=headers, timeout=30)
    resp.raise_for_status()

    op_location = resp.headers["Operation-Location"]
    job_id = op_location.split("/")[-1].split("?")[0]
    return job_id


def wait_for_job(job_id: str, poll_seconds: int = 5) -> str:
    """
    Batch job tamamlanana kadar status poll eder, son status'ü döner.
    """
    url = f"{AZURE_TRANSLATOR_ENDPOINT}/translator/document/batches/{job_id}?api-version=2024-05-01"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_TRANSLATOR_KEY,
        "Ocp-Apim-Subscription-Region": AZURE_TRANSLATOR_REGION,
    }

    while True:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        print("Azure job status:", status)
        if status in ("Succeeded", "Failed", "Cancelled"):
            return status or "Unknown"
        time.sleep(poll_seconds)


def download_translated_pdfs(local_dir: str) -> list[str]:
    """
    Target container'daki tüm PDF'leri verilen klasöre indirir,
    local path listesini döner.
    """
    _ensure_containers()
    os.makedirs(local_dir, exist_ok=True)
    container = blob_service.get_blob_container_client(TARGET_CONTAINER)

    paths: list[str] = []
    for blob in container.list_blobs():
        if not blob.name.lower().endswith(".pdf"):
            continue
        local_path = os.path.join(local_dir, os.path.basename(blob.name))
        with open(local_path, "wb") as f:
            data = container.get_blob_client(blob).download_blob()
            f.write(data.readall())
        paths.append(local_path)
    return paths


def translate_pdf_via_azure(
    local_pdf_path: str,
    from_lang: Literal["tr", "en"],
    to_lang: Literal["tr", "en"],
    download_dir: str = "./translated",
) -> list[str]:
    """
    Tek PDF için uçtan uca Azure Document Translation akışı.
    - PDF'i source container'a yükler,
    - Batch translation başlatır,
    - Job bitince target container'daki çevrilmiş PDF'leri indirir.
    """
    source_sas = upload_pdf_to_source(local_pdf_path)
    target_sas = target_container_sas()
    job_id = start_batch_translation(source_sas, target_sas, from_lang, to_lang)
    print("Started Azure translation job:", job_id)
    status = wait_for_job(job_id)
    print("Final status:", status)
    if status == "Succeeded":
        return download_translated_pdfs(download_dir)
    return []

