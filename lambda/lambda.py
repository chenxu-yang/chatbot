"""
This sample demonstrates an implementation of the Lex Code Hook Interface
in order to serve a sample bot which manages orders for flowers.
Bot, Intent, and Slot models which are compatible with this sample can be found in the Lex Console
as part of the 'OrderFlowers' template.

For instructions on how to set up and test this bot, as well as additional samples,
visit the Lex Getting Started documentation http://docs.aws.amazon.com/lex/latest/dg/getting-started.html.
"""
import math
import dateutil.parser
import datetime
import time
import os
import logging
import boto3
import json

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

sqs = boto3.client('sqs')
sqsurl = 'https://sqs.us-east-1.amazonaws.com/257949749828/chat'
# --- Helpers that build all of the responses ---


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }


def confirm_intent(session_attributes, intent_name, slots, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': message
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


# --- Helper Functions ---


def safe_int(n):
    """
    Safely convert n value to int.
    """
    if n is not None:
        return int(n)
    return n


def try_ex(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.
    Note that this function would have negative impact on performance.
    """

    try:
        return func()
    except KeyError:
        return None



def sendSQS(message):
    MessageAttribute = {
        'Title': {
            'DataType': 'String',
            'StringValue': 'The Whistler'
        }
    }
    response = sqs.send_message(QueueUrl=sqsurl, MessageBody= message)
    print("This is response",response.get('MessageId'))
    #print(response.get('MD5OfMessageBody'))
    return response

def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False


def build_validation_result(isvalid, violated_slot, message_content):
    return {
        'isValid': isvalid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }

def parse_int(n):
    try:
        return int(n)
    except ValueError:
        return float('nan')


def validate_order_dinner(cuisine_type, date, diningtime, number_of_people, location, phone_number):
    cuisine_types = ['french', 'italian', 'chinese', 'thailand', 'japanese']
    if cuisine_type is not None and cuisine_type.lower() not in cuisine_types:
        return build_validation_result(False,
                                       'Cuisine',
                                       'We do not have {}, would you like a different type of dinner?  '
                                       'Our most popular cuisine are Chinese'.format(cuisine_type))
    if date is not None:
        if not isvalid_date(date):
            return build_validation_result(False, 'DiningDate',
                                           'Sorry. We don\'t recognize the date you entered. Can you enter again?')
        elif datetime.datetime.strptime(date, '%Y-%m-%d').date() < datetime.date.today():
            return build_validation_result(False, 'DiningDate',
                                           'You can reserve a seat from tomorrow onwards.  What day would you like to choose?')


    if diningtime is not None:
        if len(diningtime) != 5:
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'DiningTime', None)

        hour, minute = diningtime.split(':')
        hour = parse_int(hour)
        minute = parse_int(minute)
        if math.isnan(hour) or math.isnan(minute):
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'DiningTime', None)

        if hour < 10 or hour > 17:
            # Outside of business hours
            return build_validation_result(False, 'DiningTime', 'Our business hours are from ten a m. to five pm. Can you specify a time during this range?')

    if phone_number is not None:
        if not phone_number.isdigit() or len(phone_number) != 10:
            return build_validation_result(False, 'PhoneNumber', 'Please input a valid phone number!')

    if number_of_people is not None:
        if int(number_of_people) > 50:
            return build_validation_result(False, 'NumberOfPeople',
                                           'Sorry we only provide restaurant recommendations less than 50 people.')
        if int(number_of_people) <= 0:
            return build_validation_result(False, 'NumberOfPeople',
                                           'Please input a valid integer number larger than zero!')

    return build_validation_result(True, None, None)


""" --- Functions that control the bot's behavior --- """


def order_dining(intent_request):
    """
    Performs dialog management and fulfillment for booking a car.
    Beyond fulfillment, the implementation for this intent demonstrates the following:
    1) Use of elicitSlot in slot validation and re-prompting
    2) Use of sessionAttributes to pass information that can be used to guide conversation
    """
    slots =try_ex(lambda: intent_request['currentIntent']['slots'])
    location = try_ex(lambda: slots['location'])
    cuisine_type = try_ex(lambda: slots['cuisine'])
    dtime = try_ex(lambda: slots['time'])
    ddate = try_ex(lambda: slots['date'])
    number_of_people = try_ex(lambda: slots['numberOfPeople'])
    phone_number =try_ex(lambda:  slots['phoneNumber'])

    confirmation_status = intent_request['currentIntent']['confirmationStatus']
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    last_confirmed_reservation = try_ex(lambda: session_attributes['lastConfirmedReservation'])
    if last_confirmed_reservation:
        last_confirmed_reservation = json.loads(last_confirmed_reservation)
    confirmation_context = try_ex(lambda: session_attributes['confirmationContext'])

    # Load confirmation history and track the current reservation.
    reservation = json.dumps({
        "Location": location,
        "Cuisine": cuisine_type,
        "DiningTime": dtime,
        "DiningDate": ddate,
        "NumberOfPeople": number_of_people,
        "PhoneNumber": phone_number
    })
    # sendSQS(reservation)
    session_attributes['currentReservation'] = reservation

    logger.debug('bookDinner at={}'.format(reservation))
    del session_attributes['currentReservation']
    session_attributes['lastConfirmedReservation'] = reservation
    sendSQS(reservation)
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Thanks, I have placed your reservation,you will receive a text on your phone'
        }
    )


def Greeting(intent_request):
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Hi there. May I help you? ex I want to make a reservation '
        }
    )


def Thanks(intent_request):
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'You are welcome!'
        }
    )


# --- Intents ---


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug(
        'dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'dinningsuggestion':
        return order_dining(intent_request)
    if intent_name == 'Greeting':
        return Greeting(intent_request)
    if intent_name == 'Thanks':
        return Thanks(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


# --- Main handler ---


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

    return dispatch(event)
