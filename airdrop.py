import asyncio
import json

from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import transfer,TransferParams,get_associated_token_address
from solders.pubkey import Pubkey
from solders.keypair import Keypair

def split_in_batches(d, n=22):
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
    mint = Pubkey.from_string("GJzuWLMkah7XW82wXfZbovRZHaKU9FmPrWn8mktUX7Po")

    with open('id.json', 'r') as file:
        secret = json.load(file)
        
    sender = Keypair.from_json(str(secret))
    sender_ata = get_associated_token_address(sender.pubkey(), mint)

    with open('balances_post_content.json', 'r') as file:
        balances_post_content = json.load(file)
    
    client = AsyncClient("https://api.devnet.solana.com")
    
    for batch in split_in_batches(balances_post_content):
        transaction = Transaction()
        
        for address, balance in batch.items():
            #print(f"Processing instruction for {address} with balance {balance}")
            
            receiver_public_key = Pubkey.from_string(address)
            receiver_ata = get_associated_token_address(receiver_public_key, mint)
            ata_info = await client.get_account_info(receiver_ata)
            if ata_info.value is None:
                print(f"No associated token account for {address}")
                continue
            
            rounded_balance = round(balance, 2)
            amount_to_transfer = int(rounded_balance * 10 ** 8)

            instruction = transfer(TransferParams(
                amount=amount_to_transfer,
                source=sender_ata,
                owner=sender.pubkey(),
                dest=receiver_ata,
                program_id=TOKEN_PROGRAM_ID,
            ))
            transaction.add(instruction)
        
        if not transaction.instructions:
            continue
        
        blockhash = (await client.get_latest_blockhash()).value.blockhash
        transaction.recent_blockhash = blockhash
        transaction.sign(sender)
        serialized_tx = transaction.serialize()
        signature = (await client.send_raw_transaction(serialized_tx)).value
        print(f"https://explorer.solana.com/tx/{signature}")

    await client.close()

asyncio.run(distribute_solana())
