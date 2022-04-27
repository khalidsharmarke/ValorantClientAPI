import asyncio
from ValorantClient import print_val_store


if __name__ == '__main__':
    try:
        asyncio.get_event_loop().run_until_complete(print_val_store())
    # intended errors
    except SystemExit as e:
        print(e)    
    # unintended errors
    except Exception as e:
        print('event loop failed')
