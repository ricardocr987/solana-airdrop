import asyncio
import json

from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from spl.token.instructions import create_associated_token_account,get_associated_token_address
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.compute_budget import set_compute_unit_price

def split_in_batches(d, n=8):
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
    mint = Pubkey.from_string("75bDMEcLCdziH4Ej5Q72LsKPzphgmU4UL3H7ck8FsfLz")

    with open('id.json', 'r') as file:
        secret = json.load(file)
        
    sender = Keypair.from_json(str(secret))
    
    with open('balances_post_content.json', 'r') as file:
        balances_post_content = json.load(file)
    
    client = AsyncClient("")
    
    for batch in split_in_batches(balances_post_content):
        transaction = Transaction(fee_payer=sender.pubkey()).add(set_compute_unit_price(5000))

        for address, balance in batch.items():
            receiver_public_key = Pubkey.from_string(address)
            init_ata_ix = create_associated_token_account(sender.pubkey(), receiver_public_key, mint)
            transaction.add(init_ata_ix)

        blockhash = await client.get_latest_blockhash()
        transaction.recent_blockhash = blockhash.value.blockhash
        transaction.sign(sender)
        serialized_tx = transaction.serialize()
        signature = (await client.send_raw_transaction(serialized_tx)).value
        await client.confirm_transaction(signature, "confirmed")
        print(f"https://explorer.solana.com/tx/{signature}")

    await client.close()

asyncio.run(prepare_atas())
