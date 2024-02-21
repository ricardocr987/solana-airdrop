The airdrop script allows sending tokens to multiple recipients on Solana, assuming that the recipients already have the mint ATA initialized, if not initialized it is skipped. The balances_post_content.json is read, splitted into batches of 22 transfers per transaction.

- config virtual env:
    - cd solana-airdrop
    - python3 -m venv virtualenv
    - source virtualenv/bin/activate
    - pip install solana
- create your own solana keypair: solana-keygen new --outfile id.json
- python airdrop.py

Note: I've also created tests to use a fake mint:
- devnet faucet: ask me or https://solfaucet.com/ or https://faucet.quicknode.com/solana/devnet
- python create_mint.py
- use the mint address printed and change it in the airdrop.py and prepare_atas.py code
- python prepare_atas.py
- python airdrop.py
