import asyncio
import json

from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import initialize_mint,get_associated_token_address,InitializeMintParams,create_associated_token_account,MintToParams, mint_to
from solders.keypair import Keypair
from solders.system_program import create_account,CreateAccountParams
from spl.token._layouts import MINT_LAYOUT
from solders.compute_budget import set_compute_unit_price

async def prepare_mint_and_distributor():
    client = AsyncClient("", "confirmed")
    
    new_mint = Keypair()
    print(f"Test mint pubkey: {new_mint.pubkey()}")

    with open('id.json', 'r') as file:
        secret = json.load(file)
    
    sender = Keypair.from_json(str(secret))
    sender_ata = get_associated_token_address(sender.pubkey(), new_mint.pubkey())

    transaction = Transaction(fee_payer=sender.pubkey()).add(set_compute_unit_price(5000))
    lamports = (await client.get_minimum_balance_for_rent_exemption(MINT_LAYOUT.sizeof())).value
    transaction.add(create_account(CreateAccountParams(
        from_pubkey=sender.pubkey(),
        to_pubkey=new_mint.pubkey(),
        owner=TOKEN_PROGRAM_ID,
        new_account_pubkey=new_mint.pubkey(),
        lamports=lamports,
        space=MINT_LAYOUT.sizeof(),
        program_id=TOKEN_PROGRAM_ID
    )))
    
    transaction.add(initialize_mint(InitializeMintParams(
        decimals=8,
        freeze_authority=sender.pubkey(),
        mint=new_mint.pubkey(),
        mint_authority=sender.pubkey(),
        program_id=TOKEN_PROGRAM_ID,
    )))

    transaction.add(create_associated_token_account(sender.pubkey(), sender.pubkey(), new_mint.pubkey()))
    
    amount_to_transfer = 1000000000 * 10 ** 8
    transaction.add(mint_to(MintToParams(
        amount=amount_to_transfer,
        dest=sender_ata,
        mint=new_mint.pubkey(),
        mint_authority=sender.pubkey(),
        program_id=TOKEN_PROGRAM_ID,
    )))

    blockhash = await client.get_latest_blockhash()
    transaction.recent_blockhash = blockhash.value.blockhash
    transaction.sign(sender, new_mint)
    serialized_tx = transaction.serialize()
    signature = (await client.send_raw_transaction(serialized_tx)).value
    print(f"https://explorer.solana.com/tx/{signature}?cluster=devnet")
    await client.confirm_transaction(signature, "confirmed")
    
    await client.close()

asyncio.run(prepare_mint_and_distributor())
