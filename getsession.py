from telethon.sync import TelegramClient

# 1. You must get your own api_id and api_hash from https://my.telegram.org
# Log in -> API development tools -> Create a new application
API_ID = 20230268  # Replace with your actual integer API ID
API_HASH = '72c3bf193f58a0e4b83bfd2b78dadf8c' # Replace with your actual string API Hash

# 2. Define the name of your session file
# This will create a file named 'my_bot_account.session' in your current directory
SESSION_NAME = 'qunixivll'

async def main():
    # Initialize the Telegram Client
    # The first parameter is the session name
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    # Start the client. This will prompt for a phone number and code 
    # in the terminal if the .session file doesn't exist yet.
    await client.start()
    
    print(f"✅ Successfully logged in! Session saved as '{SESSION_NAME}.session'")
    
    # Optional: Send a test message to your "Saved Messages" to verify it works
    me = await client.get_me()
    await client.send_message('me', f'Hello! Session {SESSION_NAME} is active.')
    print(f"Logged in as: {me.first_name} (ID: {me.id})")
    
    # Disconnect when done (or you can use client.run_until_disconnected() to keep it running)
    await client.disconnect()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
