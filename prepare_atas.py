import asyncio
import json

from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from spl.token.instructions import create_associated_token_account,get_associated_token_address
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.compute_budget import set_compute_unit_price
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts

def split_in_batches(d, n=5):
    it = iter(d)
    batch = {}
    for key in it:
        batch[key] = d[key]
        if len(batch) == n:
            yield batch
            batch = {}
    if batch:
        yield batch
        
async def prepare_atas():
    mint = Pubkey.from_string("3hAY8CoHkaNUB76hedQyNER8Zrp989heEj72PiXKw4Lm")

    with open('id.json', 'r') as file:
        secret = json.load(file)
        
    sender = Keypair.from_json(str(secret))
    
    with open('owner_and_rewards.json', 'r') as file:
        owner_and_rewards = json.load(file)
    
    client = AsyncClient("", Confirmed)
    balances_post_content = {}

    for batch in split_in_batches(owner_and_rewards):
        transaction = Transaction(fee_payer=sender.pubkey()).add(set_compute_unit_price(5000))

        for address, balance in batch.items():
            receiver_ata = get_associated_token_address(Pubkey.from_string(address), mint)
            balances_post_content.update({ str(receiver_ata): balance })
            
            receiver_public_key = Pubkey.from_string(address)
            init_ata_ix = create_associated_token_account(sender.pubkey(), receiver_public_key, mint)
            transaction.add(init_ata_ix)

        for _ in range(5):
            try:
                blockhash = await client.get_latest_blockhash()
                transaction.recent_blockhash = blockhash.value.blockhash
                transaction.sign(sender)
                serialized_tx = transaction.serialize()
                opts = TxOpts(skip_confirmation = False, preflight_commitment = Confirmed)
                signature = (await client.send_raw_transaction(serialized_tx, opts)).value
                await client.confirm_transaction(signature, Confirmed)
                
                print(f"Transaction successful: https://explorer.solana.com/tx/{signature}")
                break
            
            except Exception as e:
                print(f"Transaction failed with error: {e}. Retrying...")
                await asyncio.sleep(1)
        
    with open("balances_post_content.json", "w") as file:
        json.dump(balances_post_content, file, indent=4)

    await client.close()

asyncio.run(prepare_atas())
