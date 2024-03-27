import asyncio
import json
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
    # note: not getting last block to avoid LongTermStorageSlotSkippedMessage error
    block_height = (await client.get_block_height()).value - 5
    block_data = (await client.get_block(block_height, max_supported_transaction_version=0)).value
    if block_data.transactions is None:
        return None
    
    transactions_info = [
        {'fee': tx.meta.fee, 'compute_units_consumed': tx.meta.compute_units_consumed}
        for tx in block_data.transactions
        if tx.meta.fee > 5000 and tx.meta.compute_units_consumed is not None and tx.meta.compute_units_consumed > 0
    ]
    
    priority_fees = [
        (tx_info['fee'] - 5000) / tx_info['compute_units_consumed']
        for tx_info in transactions_info
    ]
    priority_fees.sort()

    median_priority_fee = 0
    if priority_fees:
        n = len(priority_fees)
        if n % 2 == 0:
            median_priority_fee = (priority_fees[n // 2 - 1] + priority_fees[n // 2]) / 2
        else:
            median_priority_fee = priority_fees[n // 2]

    print("Median Priority Fee:", round(int(median_priority_fee * 10 ** 6), 0))
    # convert to micro-lamports
    return round(int(median_priority_fee * 10 ** 6), 0)

# note: batch could be bigger, but spending more CU increase the time it takes 
# for the transaction to be included in a block, so bigger txn, less likely to get confirmed
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
        # in case we receive closed associated token accounts (it should not happen)
        addresses_to_remove = []
        
        try:
            transaction = Transaction(fee_payer=sender.pubkey()).add(set_compute_unit_price(priority_fee))
                      
            for address, balance in batch.items():
                receiver_ata = Pubkey.from_string(address)
                
                balance_info = await client.get_balance(receiver_ata)
                if balance_info.value is None:
                    print(f"No associated token account for {address}")
                    addresses_to_remove.append(address)
                    continue
                
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
            
            # Remove addresses without ATAs from the batch
            for address in addresses_to_remove:
                del batch[address]
            
            # If there is only set_compute_unit_price instruction, the distribution is finished
            if len(transaction.instructions) == 1:
                return True

            blockhash = (await client.get_latest_blockhash()).value.blockhash
            transaction.recent_blockhash = blockhash
            transaction.sign(sender)
            serialized_tx = transaction.serialize()
            signature = (await client.send_raw_transaction(serialized_tx)).value
            await client.confirm_transaction(signature, "confirmed")
            print(f"Transaction confirmed: https://explorer.solana.com/tx/{signature}")
            return True
        
        except Exception as e:
            print(f"Attempt {retry_count + 1}: Error - {e}")
            retry_count += 1
            await asyncio.sleep(5)
    
    return False

async def main():
    client = AsyncClient("")
    priority_fee = await get_priority_fee(client)
    
    with open('id.json', 'r') as file:
        secret = json.load(file)
        
    mint = Pubkey.from_string("3hAY8CoHkaNUB76hedQyNER8Zrp989heEj72PiXKw4Lm")
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
            print("A batch failed 5 times. Stopping distribution.")
            break
        
        successful_transactions.update(batch)
        with open(cache_file, "w") as file:
            json.dump(successful_transactions, file, indent=4)

    if all_batches_successful and os.path.exists(cache_file):
        os.remove(cache_file)
        print("All batches processed successfully.")

    await client.close()

asyncio.run(main())
