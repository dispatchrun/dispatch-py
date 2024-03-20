from fastapi import FastAPI
import logging
from cloudevents.http import CloudEvent

from dispatch.app import Dispatch
from dispatch import gather, call


dispatch = Dispatch()


@dispatch.function
async def process(event: CloudEvent):
    print(f"Processing {event}")


archive_count = 0


@dispatch.function
async def archive(event: CloudEvent):
    logging.info("archiving event")
    global archive_count
    archive_count += 1
    print(f"Archiving: {archive_count}")


@dispatch.function
async def sequence(event: CloudEvent):
    await archive(event)
    await process(event)


@dispatch.function
async def concurrent(event: CloudEvent):
    await gather(
        archive(event),
        process(event),
    )


@dispatch.function
async def handler(event: CloudEvent):
    logging.info("handling event", event)
    #await gather(
    #        sequence(event),
    #        concurrent(event),
    #)
    #await call(archive.build_call(event))
    await archive(event)
    


if __name__ == "__main__":
    attributes = {
        "type": "com.example.sampletype1",
        "source": "https://example.com/event-producer",
    }
    data = {"message": "Hello World!"}
    event = CloudEvent(attributes, data)

    dispatch.run(handler, event)
