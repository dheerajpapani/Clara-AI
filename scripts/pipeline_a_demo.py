import os
import json
import argparse
from pipeline_utils import Extractor

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input json (demo transcript)")
    parser.add_argument("--account_id", required=False, help="Account ID for storage. Auto-generated if omitted.")
    args = parser.parse_args()
    
    if not args.account_id:
        base_dir = "outputs/accounts"
        os.makedirs(base_dir, exist_ok=True)
        existing = [d for d in os.listdir(base_dir) if d.startswith("account-")]
        if not existing:
            account_id = "account-1"
        else:
            nums = []
            for d in existing:
                try:
                    nums.append(int(d.split("-")[1]))
                except ValueError:
                    pass
            next_num = max(nums) + 1 if nums else 1
            account_id = f"account-{next_num}"
        print(f"No account_id provided. Auto-generated: {account_id}")
    else:
        account_id = args.account_id

    from pipeline_utils import transcribe_media
    
    print(f"Loading input data: {args.input}")
    transcript_text = ""
    input_lower = args.input.lower()
    
    if input_lower.endswith(('.mp4', '.m4a', '.mp3', '.wav', '.flac')):
        print("Detected media file. Running Whisper transcription...")
        transcript_text = transcribe_media(args.input)
    elif input_lower.endswith('.json'):
        with open(args.input, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for segment in data:
            speaker = segment.get("speaker_name", "Speaker")
            text = segment.get("sentence", "")
            transcript_text += f"{speaker}: {text}\n"
    else:
        # Assume standard text file
        with open(args.input, 'r', encoding='utf-8') as f:
            transcript_text = f.read()

    print("Initializing Extractor...")
    extractor = Extractor()
    
    print("Extracting Account Memo v1...")
    memo_v1 = extractor.extract_demo_memo(transcript_text, account_id)
    
    # We no longer strictly print fallback messages natively in this script
    # as the Extractor class handles all logging locally via the `logging` module.

    memo_v1['account_id'] = account_id

    print("Generating Agent Spec v1...")
    spec_v1 = extractor.extract_agent_spec(memo_v1, version="v1")

    # Save to outputs
    out_dir = f"outputs/accounts/{account_id}/v1"
    os.makedirs(out_dir, exist_ok=True)

    memo_path = os.path.join(out_dir, "account_memo.json")
    spec_path = os.path.join(out_dir, "agent_spec.json")

    with open(memo_path, 'w', encoding='utf-8') as f:
        json.dump(memo_v1, f, indent=2)
        
    with open(spec_path, 'w', encoding='utf-8') as f:
        json.dump(spec_v1, f, indent=2)

    print(f"Pipeline A Demo processing complete. Saved to {out_dir}")

if __name__ == "__main__":
    main()
