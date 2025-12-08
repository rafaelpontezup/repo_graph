import json
import logging
from datetime import datetime
from threading import Lock

from cnpj_alphanum_python.utils.constants import OUTPUT_AI_TOKEN_USAGE_PATH, LLM_MODEL
from cnpj_alphanum_python.utils.json_utils import read_json_file, save_json_file

import tiktoken

_token_usage_lock = Lock()


def count_tokens(text, model=LLM_MODEL):
    """
    Count the number of tokens in a string using tiktoken for a given model.
    Returns the number of tokens, or 0 if tiktoken is not available.
    """
    try:
        tokenizer = tiktoken.encoding_for_model(model)
        return len(tokenizer.encode(text))
    except Exception as e:
        logging.warning(f"Error counting tokens: {e}")
        return 0


def save_ai_token_usage(input=None, output=None, execution_id=None):
    """
    Save or update the AI token usage for each remote execution.
    """
    payload_str = json.dumps(input, ensure_ascii=False) if input is not None else ""
    response_str = json.dumps(output, ensure_ascii=False) if output is not None else ""

    execution_id = _normalize_execution_id(execution_id)
    tokens_sent = count_tokens(payload_str) if payload_str else 0
    tokens_received = count_tokens(response_str) if response_str else 0
    payload_size = len(payload_str.encode("utf-8")) if payload_str else 0
    response_size = len(response_str.encode("utf-8")) if response_str else 0
    timestamp = datetime.now().isoformat()

    with _token_usage_lock:
        try:
            data_list = read_json_file(OUTPUT_AI_TOKEN_USAGE_PATH)
        except Exception:
            data_list = []
        found = False
        for data in data_list:
            if data.get("execution_id") == execution_id:
                if output is not None:
                    data["tokens_received"] = tokens_received
                    data["output_size"] = response_size
                    logging.info(f"{execution_id} | RQC | AI Token Usage (tokens_received={tokens_received})")
                found = True
                break
        if not found:
            data = {
                "timestamp": timestamp,
                "execution_id": execution_id,
                "tokens_sent": tokens_sent if input is not None else 0,
                "tokens_received": 0,
                "model": LLM_MODEL,
                "input_size": payload_size if input is not None else 0,
                "output_size": 0
            }
            data_list.append(data)
            logging.info(f"{execution_id} | RQC | AI Token Usage (tokens_sent={tokens_sent})")
        save_json_file(OUTPUT_AI_TOKEN_USAGE_PATH, data_list)


def get_consolidated_token_usage():
    """
    Get consolidated token usage data from the saved token usage file.
    Returns a dict with individual executions and totals.
    """
    try:
        data_list = read_json_file(OUTPUT_AI_TOKEN_USAGE_PATH)
    except Exception:
        return {
            "ai_executions": [],
            "totalTokenSent": 0,
            "totalTokenReceived": 0
        }
    
    total_tokens_sent = 0
    total_tokens_received = 0
    ai_executions = []
    
    for data in data_list:
        tokens_sent = data.get("tokens_sent", 0)
        tokens_received = data.get("tokens_received", 0)
        
        total_tokens_sent += tokens_sent
        total_tokens_received += tokens_received
        
        ai_executions.append({
            "timestamp": data.get("timestamp"),
            "execution_id": data.get("execution_id"),
            "tokens_sent": tokens_sent,
            "tokens_received": tokens_received,
            "model": data.get("model"),
            "input_size": data.get("input_size", 0),
            "output_size": data.get("output_size", 0)
        })
    
    return {
        "ai_executions": ai_executions,
        "totalTokenSent": total_tokens_sent,
        "totalTokenReceived": total_tokens_received
    }


def _normalize_execution_id(execution_id):
    """
    Normalize the execution_id to a string. If it's a list or dict, extract the id.
    If it's empty or invalid, return 'unknown' and log a warning.
    """
    if isinstance(execution_id, (list, dict)):
        if isinstance(execution_id, list) and execution_id:
            execution_id = str(execution_id[0])
        elif isinstance(execution_id, dict) and "execution_id" in execution_id:
            execution_id = str(execution_id["execution_id"])
        else:
            execution_id = str(execution_id)
    if not execution_id or execution_id in ("[]", "{}", ""):
        logging.warning("Empty or invalid execution_id when persisting token usage.")
        execution_id = "unknown"
    return execution_id
