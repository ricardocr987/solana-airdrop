import asyncio
import json
import numpy as np

from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import transfer,TransferParams,get_associated_token_address
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.compute_budget import set_compute_unit_price

async def get_priority_fee(client: AsyncClient):
    block_height = (await client.get_block_height()).value
    block_data = (await client.get_block(block_height, max_supported_transaction_version=0)).value
    if block_data.transactions is None:
        return None
    
    fees = [
        tx.meta.fee
        for tx in block_data.transactions
        if tx.meta is not None and tx.meta.fee is not None
    ]
    
    # note: deleted base fees to get median priority fee
    return int(np.median(fees)) - 5000 if fees else None

def split_in_batches(d, n=18):
    it = iter(d)
    batch = {}
    for key in it:
        batch[key] = d[key]
        if len(batch) == n:
            yield batch
            batch = {}
    if batch:
        yield batch
   
async def distribute_solana():
    mint = Pubkey.from_string("DkfmExBaNvggTYxvMi3mnVSS3DiQZUi8tapGqbzLeByF")
    client = AsyncClient("https://api.devnet.solana.com")

    with open('id.json', 'r') as file:
        secret = json.load(file)
    
    priority_fee = await get_priority_fee(client)
    print(priority_fee)
    
    sender = Keypair.from_json(str(secret))
    sender_ata = get_associated_token_address(sender.pubkey(), mint)

    with open('balances_post_content.json', 'r') as file:
        balances_post_content = json.load(file)
    
    for batch in split_in_batches(balances_post_content):
        transaction = Transaction(fee_payer=sender.pubkey()).add(set_compute_unit_price(priority_fee))
        
        for address, balance in batch.items():
            #we will get atas directly from the indexer
            receiver_public_key = Pubkey.from_string(address)
            receiver_ata = get_associated_token_address(receiver_public_key, mint)
            rounded_balance = round(balance, 8)
            amount_to_transfer = int(rounded_balance * 10 ** 8)

            instruction = transfer(TransferParams(
                amount=amount_to_transfer,
                source=sender_ata,
                owner=sender.pubkey(),
                dest=receiver_ata,
                program_id=TOKEN_PROGRAM_ID,
            ))
            transaction.add(instruction)
        
        blockhash = (await client.get_latest_blockhash()).value.blockhash
        transaction.recent_blockhash = blockhash
        transaction.sign(sender)
        serialized_tx = transaction.serialize()
        signature = (await client.send_raw_transaction(serialized_tx)).value
        await client.confirm_transaction(signature, "confirmed")
        print(f"https://explorer.solana.com/tx/{signature}")

    await client.close()

asyncio.run(distribute_solana())
