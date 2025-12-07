import argparse
import json
import random
import time
import requests
import os
from pathlib import Path

from app.services.filesystem import get_random_titlecard_filename


def queue_prompt(url, prompt):
    p = {"prompt": prompt}
    data = json.dumps(p).encode('utf-8')
    prompt_url = f"{url}/prompt"
    try:
        r = requests.post(prompt_url, data=data)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as ex:
        print(f'POST {prompt_url} failed: {ex}')
        return None

def get_queue(url):
    queue_url = f"{url}/queue"
    try:
        r = requests.get(queue_url)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as ex:
        print(f'GET {queue_url} failed: {ex}')
        return None


def get_history(url, prompt_id):
    history_url = f"{url}/history/{prompt_id}"
    try:
        r = requests.get(history_url)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as ex:
        print(f'GET {history_url} failed: {ex}')
        return None


def upload_image(url: str, image_path: Path, timeout: float = 60.0) -> bool:
    """Upload a PNG image to the ComfyUI upload endpoint.

    Returns True on success, False otherwise.
    """

    upload_url = f"{url}/upload/image"

    if not image_path.exists():
        print(f"[ERROR] Image not found at: {image_path}")
        return False

    try:
        print(f"[UPLOAD] -> {upload_url} :: {image_path.name}")
        with image_path.open("rb") as f:
            files = {"image": (image_path.name, f, "image/png")}
            data = {"type": "input"}
            resp = requests.post(upload_url, files=files, data=data, timeout=timeout)
        if resp.status_code == 200:
            return True
        else:
            print(f"[ERROR] Upload failed for {image_path} (status {resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        print(f"[ERROR] Exception during upload for {image_path}: {e}")

    return False


def main(ip, port, filepath, prompt=None, dest=None):
    url = f"http://{ip}:{port}"

    with open(filepath, 'r') as file:
        prompt_text = json.load(file)

    # Print the prompt text, either change the text here or in the JSON file
    if prompt is not None:
        prompt_text["6"]["inputs"]["text"] = prompt
    print(f'Prompt: {prompt_text["6"]["inputs"]["text"]}')

    # Set the seed for our KSampler node, always generate a new seed
    prompt_text["57"]["inputs"]["noise_seed"] = random.randint(0, 1000000000000000)
    print(f'Seed: {prompt_text["57"]["inputs"]["noise_seed"]}')

    # Choose a titlecard image using the helper, biased toward top arena performers.
    titlecard_name = get_random_titlecard_filename()
    if titlecard_name is None:
        print("No titlecard images available to select.")
        return

    # Upload the selected titlecard from the titlecards directory, then set it on the workflow.
    image_path = Path(r"E:\Scarlett\titlecards") / titlecard_name
    if not upload_image(url, image_path):
        print("Aborting due to image upload failure.")
        return

    prompt_text["52"]["inputs"]["image"] = titlecard_name
    print(f'Random image: {prompt_text["52"]["inputs"]["image"]}')

    response1 = queue_prompt(url, prompt_text)
    if response1 is None:
        print("Failed to queue the prompt.")
        return

    prompt_id = response1['prompt_id']
    print(f'Prompt ID: {prompt_id}')
    print('-' * 20)

    while True:
        time.sleep(5)
        queue_response = get_queue(url)
        if queue_response is None:
            continue

        queue_pending = queue_response.get('queue_pending', [])
        queue_running = queue_response.get('queue_running', [])

        # Check position in queue
        for position, item in enumerate(queue_pending):
            if item[1] == prompt_id:
                print(f'Queue running: {len(queue_running)}, Queue pending: {len(queue_pending)}, Workflow is in position {position + 1} in the queue.')

        # Check if the prompt is currently running
        for item in queue_running:
            if item[1] == prompt_id:
                print(f'Queue running: {len(queue_running)}, Queue pending: {len(queue_pending)}, Workflow is currently running.')
                break

        if not any(prompt_id in item for item in queue_pending + queue_running):
            break

    history_response = get_history(url, prompt_id)
    if history_response is None:
        print("Failed to retrieve history.")
        return

    output_info = history_response.get(prompt_id, {}).get('outputs', {}).get('64', {}).get('gifs', [{}])[0]
    comfy_filename = output_info.get('filename', 'unknown')
    subfolder = output_info.get('subfolder', '')

    if comfy_filename == 'unknown':
        print("Failed to retrieve output. Check history response format for the corrrect node number")
        print(history_response.get(prompt_id, {}))
        return

    if subfolder:
        output_url = f"{url}/output/{subfolder}/{comfy_filename}"
    else:
        output_url = f"{url}/output/{comfy_filename}"

    print(f"Output URL: {output_url}")

    # Determine download directory
    if dest is not None and dest.strip() == "":
        dest = None

    download_dir = dest if dest else os.getcwd()
    try:
        os.makedirs(download_dir, exist_ok=True)
    except OSError as ex:
        print(f"Failed to create destination directory '{download_dir}': {ex}")
        return

    # Locally, prefix the filename with the titlecard stem so we can trace back
    # which source image generated the output.
    try:
        titlecard_stem = Path(titlecard_name).stem
        local_filename = f"{titlecard_stem}_{comfy_filename}"
    except Exception:
        local_filename = comfy_filename

    local_path = os.path.join(download_dir, local_filename)

    # Download the file
    try:
        with requests.get(output_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        print(f"Downloaded to: {local_path}")
    except requests.exceptions.RequestException as ex:
        print(f"Failed to download output: {ex}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Add a prompt to the queue and wait for the output.')
    parser.add_argument('--ip', type=str, required=True, help='The public IP address of the pod (you can see this in the "TCP Port Mappings" tab when you click the "connect" button on Runpod.io)')
    parser.add_argument('--port', type=int, required=True, help='The external port of the pod (you can see this in the "TCP Port Mappings" tab when you click the "connect" button on Runpod.io)')
    parser.add_argument('--filepath', type=str, required=True, help='The path to the JSON file containing the workflow in api format')
    parser.add_argument('--prompt', type=str, required=False, help='The prompt to use for the workflow', default=None, nargs='*')
    parser.add_argument('--dest', type=str, required=False, help='Destination directory to save the output file. If omitted or empty, saves to the current directory.', default=None)
    parser.add_argument('--n', type=int, required=False, default=1, help='Number of titlecards to generate. Use -1 to run indefinitely.')

    args = parser.parse_args()

    count = 0
    while True:
        count += 1
        print(f"\n=== Titlecard run {count} ===")
        main(
            args.ip,
            args.port,
            args.filepath,
            ' '.join(args.prompt) if args.prompt is not None else None,
            args.dest,
        )

        if args.n == -1:
            continue
        if count >= args.n:
            break