import os
import json
import argparse
from deepdiff import DeepDiff
from pipeline_utils import Extractor

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--account_id", required=True, help="Account ID for storage")
    parser.add_argument("--input", required=True, help="Path to onboarding audio transcript or chat text")
    args = parser.parse_args()

    v1_dir = f"outputs/accounts/{args.account_id}/v1"
    v2_dir = f"outputs/accounts/{args.account_id}/v2"
    os.makedirs(v2_dir, exist_ok=True)

    memo_v1_path = os.path.join(v1_dir, "account_memo.json")
    if not os.path.exists(memo_v1_path):
        print(f"Error: Could not find v1 memo at {memo_v1_path}")
        return
        
    print("Loading Account Memo v1...")
    with open(memo_v1_path, 'r', encoding='utf-8') as f:
        memo_v1 = json.load(f)

    onboarding_data = ""
    if args.input and os.path.exists(args.input):
        print(f"Loading input data: {args.input}")
        input_lower = args.input.lower()
        
        if input_lower.endswith(('.mp4', '.m4a', '.mp3', '.wav', '.flac')):
            print("Detected media file. Running Whisper transcription...")
            from pipeline_utils import transcribe_media
            onboarding_data = transcribe_media(args.input)
        elif input_lower.endswith('.json'):
            with open(args.input, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Support array of segments or direct text parsing
            if isinstance(data, list):
                for segment in data:
                    speaker = segment.get("speaker_name", "Speaker")
                    text = segment.get("sentence", "")
                    onboarding_data += f"{speaker}: {text}\n"
            else:
                onboarding_data = json.dumps(data)
        else:
            with open(args.input, 'r', encoding='utf-8') as f:
                onboarding_data = f.read()

    if not onboarding_data.strip():
        print(f"Warning: No valid transcript or chat found at {args.input}. Proceeding with empty string.")

    print("Initializing Extractor...")
    extractor = Extractor()

    print("Extracting Account Memo v2...")
    memo_v2 = extractor.extract_onboarding_updates(onboarding_data, memo_v1)

    # Using logging module instead of native print statements for robustness
    memo_v2['account_id'] = args.account_id

    print("Generating Agent Spec v2...")
    spec_v2 = extractor.extract_agent_spec(memo_v2, version="v2")

    # Generate changelog
    print("Generating Changelog...")
    diff = DeepDiff(memo_v1, memo_v2, ignore_order=True)
    
    # Format Changelog as JSON
    changelog = json.loads(diff.to_json())

    # Save to outputs
    memo_v2_path = os.path.join(v2_dir, "account_memo.json")
    spec_v2_path = os.path.join(v2_dir, "agent_spec.json")
    changelog_path = os.path.join(v2_dir, "changelog.json")

    with open(memo_v2_path, 'w', encoding='utf-8') as f:
        json.dump(memo_v2, f, indent=2)
        
    with open(spec_v2_path, 'w', encoding='utf-8') as f:
        json.dump(spec_v2, f, indent=2)
        
    with open(changelog_path, 'w', encoding='utf-8') as f:
        json.dump(changelog, f, indent=2)

    print(f"Pipeline B Onboarding processing complete. Saved to {v2_dir}")

if __name__ == "__main__":
    main()
