import asyncio
import json
import numpy as np
import os

from typing import Dict
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

# note: the batch could be bigger but when more CU wasted, less likely the transaction is confirmed
def split_in_batches(d, n=15):
    it = iter(d)
    batch = {}
    for key in it:
        batch[key] = d[key]
        if len(batch) == n:
            yield batch
            batch = {}
    if batch:
        yield batch
        
async def distribute(
    client: AsyncClient,
    sender: Keypair,
    sender_ata: Pubkey,
    mint: Pubkey,
    batch: Dict[str, float],
    priority_fee: int,
    max_retries: int = 5,
) -> bool:
    retry_count = 0
    while retry_count < max_retries:
        try:
            transaction = Transaction(fee_payer=sender.pubkey()).add(set_compute_unit_price(priority_fee))
                      
            for address, balance in batch.items():
                # note: modify this, we will get atas directly from the indexer
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
            print(f"Transaction confirmed: https://explorer.solana.com/tx/{signature}")
            return True
        
        except Exception:
            print(f"Attempt {retry_count + 1}: Error")
            retry_count += 1
            await asyncio.sleep(5)
    
    print("Failed to process batch after maximum retries.")
    return False

async def main():
    client = AsyncClient("https://api.devnet.solana.com")
    priority_fee = await get_priority_fee(client)
    
    with open('id.json', 'r') as file:
        secret = json.load(file)
        
    mint = Pubkey.from_string("DkfmExBaNvggTYxvMi3mnVSS3DiQZUi8tapGqbzLeByF")
    sender = Keypair.from_json(str(secret))
    sender_ata = get_associated_token_address(sender.pubkey(), mint)
    
    with open('balances_post_content.json', 'r') as file:
        balances_post_content = json.load(file)
        
    cache_file = "successful_transactions.json"
    successful_transactions = {}
    
    all_batches_successful = True
    for batch in split_in_batches(balances_post_content):
        success = await distribute(client, sender, sender_ata, mint, batch, priority_fee)

        if not success:
            all_batches_successful = False
            print("A batch failed to process. Stopping distribution.")
            break
        
        successful_transactions.update(batch)
        with open(cache_file, "w") as file:
            json.dump(successful_transactions, file, indent=4)

    if all_batches_successful and os.path.exists(cache_file):
        os.remove(cache_file)
        print("All batches processed successfully.")

    await client.close()

asyncio.run(main())
