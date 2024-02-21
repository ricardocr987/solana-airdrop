The airdrop script allows you to do send tokens to multiple recipents on Solana, assuming recipents already have the mint ATA initialized, if not initialized is skipped. The balances_post_content.json is read, splitted in batches of 22 transfers (ie: each transaction does 22 transfers).

- packages used: solders & solana
- activate virtual env
- create your own solana keypair: solana-keygen new --outfile id.json
- python airdrop.py

Note: I've also created tests to use a fake mint:
- devnet faucet: ask me or https://faucet.quicknode.com/solana/devnet or https://solfaucet.com/
- python create_mint.py
- use the mint address printed and change it in the airdrop.py and prepare_atas.py code
- python prepare_atas.py
- python airdrop.py