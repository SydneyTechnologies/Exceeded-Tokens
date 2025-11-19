import asyncio
import httpx
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def initiate_opus_job(
    api_base_url: str,
    workflow_id: str,
    title: str,
    description: str,
) -> Optional[str]:
    """
    Call POST /job/initiate and return jobExecutionId (or None on error).
    """
    url = f"{api_base_url}/job/initiate"
    payload = {
        "workflowId": workflow_id,
        "title": title,
        "description": description,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)

        if resp.status_code == 200:
            data = resp.json()
            # Adjust this key based on actual API response shape
            job_execution_id = (
                data.get("jobExecutionId")
                or data.get("job_execution_id")
                or data.get("id")
            )
            if not job_execution_id:
                logger.error(
                    f"Initiate job: missing jobExecutionId in response: {data}"
                )
                return None

            return job_execution_id

        logger.error(f"Initiate job failed {resp.status_code}: {resp.text}")
        return None

    except httpx.TimeoutException:
        logger.error("Timeout calling /job/initiate")
        return None
    except Exception as e:
        logger.error(f"Error calling /job/initiate: {e}")
        return None


async def execute_opus_job(
    api_base_url: str,
    job_execution_id: str,
    webhook_payload: Dict[str, Any],
) -> bool:
    """
    Call POST /job/execute with the jobExecutionId and webhook_payload.
    Returns True if request was accepted (2xx), False otherwise.
    """
    url = f"{api_base_url}/job/execute"
    payload = {
        "jobExecutionId": job_execution_id,
        "jobPayloadSchemaInstance": {
            "webhook_payload": {
                "value": webhook_payload,
                "type": "object",
            }
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)

        if 200 <= resp.status_code < 300:
            return True

        logger.error(f"Execute job failed {resp.status_code}: {resp.text}")
        return False

    except httpx.TimeoutException:
        logger.error("Timeout calling /job/execute")
        return False
    except Exception as e:
        logger.error(f"Error calling /job/execute: {e}")
        return False


async def get_opus_job_status(
    api_base_url: str,
    job_execution_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Call GET /job/{job_id} and return the JSON status payload (or None on error).
    """
    url = f"{api_base_url}/job/{job_execution_id}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)

        if resp.status_code == 200:
            return resp.json()

        logger.error(f"Get job status failed {resp.status_code}: {resp.text}")
        return None

    except httpx.TimeoutException:
        logger.error("Timeout calling /job/{job_id}")
        return None
    except Exception as e:
        logger.error(f"Error calling /job/{job_execution_id}: {e}")
        return None


async def run_opus_sales_workflow(
    api_base_url: str,
    user_enquiry: str,
    lead_name: str,
    lead_email: str,
    lead_phone: str,
    workflow_id: str = "fCfm1qu3l4tCVR38",
) -> str:
    # 1) Initiate job
    job_id = await initiate_opus_job(
        api_base_url=api_base_url,
        workflow_id=workflow_id,
        title="Run AI Sales from API",
        description="This job will run from an API call",
    )

    if not job_id:
        return "❌ Failed to start Opus workflow."

    # 2) Execute job
    webhook_payload = {
        "user_enquiry": user_enquiry,
        "lead_name": lead_name,
        "lead_email": lead_email,
        "lead_phone": lead_phone,
    }

    executed = await execute_opus_job(
        api_base_url=api_base_url,
        job_execution_id=job_id,
        webhook_payload=webhook_payload,
    )

    if not executed:
        return f"❌ Failed to execute job {job_id}."

    # 3) Poll Opus until the workflow execution is completed (or fails/times out)
    poll_interval_seconds = 2.0
    max_polls = 60  # ~2 minutes total
    last_status: Optional[Dict[str, Any]] = None

    def _job_is_completed(status_payload: Dict[str, Any]) -> bool:
        """
        Determine if the job is completed based on the response shape.

        The sample payload looks like:
        {
            "title": "...",
            "jobExecutionId": "3634",
            "workflowId": "...",
            "audit": {
                "nb_nodes": 17,
                "nb_executed_nodes": 17,
                "nb_failed_nodes": 0,
                ...
            }
        }
        """
        audit = status_payload.get("audit") or {}
        nb_nodes = audit.get("nb_nodes")
        nb_executed_nodes = audit.get("nb_executed_nodes")
        nb_failed_nodes = audit.get("nb_failed_nodes", 0)

        # If any nodes failed, we consider the job not successfully completed.
        if isinstance(nb_failed_nodes, int) and nb_failed_nodes > 0:
            return False

        if isinstance(nb_nodes, int) and isinstance(nb_executed_nodes, int):
            return nb_nodes == nb_executed_nodes

        # Fallback: look for a generic execution status flag
        execution_status = (
            status_payload.get("execution_status")
            or status_payload.get("status")
            or status_payload.get("state")
        )
        if isinstance(execution_status, str):
            return execution_status.upper() in {"COMPLETED", "SUCCEEDED", "SUCCESS"}

        return False

    def _job_has_failed(status_payload: Dict[str, Any]) -> bool:
        audit = status_payload.get("audit") or {}
        nb_failed_nodes = audit.get("nb_failed_nodes", 0)
        if isinstance(nb_failed_nodes, int) and nb_failed_nodes > 0:
            return True

        execution_status = (
            status_payload.get("execution_status")
            or status_payload.get("status")
            or status_payload.get("state")
        )
        if isinstance(execution_status, str):
            return execution_status.upper() in {"FAILED", "ERROR"}

        return False

    for _ in range(max_polls):
        last_status = await get_opus_job_status(
            api_base_url=api_base_url, job_execution_id=job_id
        )

        if not last_status:
            # Couldn't retrieve status this time; wait and retry.
            await asyncio.sleep(poll_interval_seconds)
            continue

        if _job_has_failed(last_status):
            return f"❌ Job {job_id} failed. Final status payload: {last_status}"

        if _job_is_completed(last_status):
            return f"✅ Job {job_id} completed successfully."

        await asyncio.sleep(poll_interval_seconds)

    # If we exit the loop, we timed out waiting for completion.
    status_str = "unknown"
    if isinstance(last_status, dict):
        status_str = (
            last_status.get("execution_status")
            or last_status.get("status")
            or last_status.get("state")
            or status_str
        )

    return (
        f"⏳ Job {job_id} is still running after "
        f"{int(poll_interval_seconds * max_polls)} seconds. "
        f"Last known status: {status_str}"
    )
