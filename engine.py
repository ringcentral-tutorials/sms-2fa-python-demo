from ringcentral import SDK
import os
import json
#from os.path import join, dirname
from hashlib import sha256
import math
import datetime
import time
from random import randint

import sqlite3
from sqlite3 import Error
from flask import g

MAX_FAILURE = 2

USER_DATABASE = 'db/users.db'
def enum(**enums):
    return type('Enum', (), enums)

ResCode = enum(OK=0,FAILED=1,LOCKED=2,INVALID=3,UNKNOWN=4,MAX_FAILURE=5)

from dotenv import load_dotenv
dotenv_path = '.env'
load_dotenv(dotenv_path)

def getSeed():
    try:
        conn = sqlite3.connect(USER_DATABASE)
        query = 'CREATE TABLE if not exists seeds (id INT PRIMARY KEY, seed DateTime NOT NULL)'
        cur = conn.cursor()
        cur.execute(query)
        conn.commit()
        dateStr = str(datetime.datetime.now())
        id = str(generateRandomCode(5))
        query = "INSERT INTO seeds VALUES (" + id + ",'" + dateStr + "')";
        cur = conn.cursor()
        cur.execute(query)
        conn.commit()
        conn.close()
        seedObj = {}
        seedObj['id'] = id
        seedObj['seed'] = dateStr
        return json.dumps(seedObj)
    except Error as e:
        return databaseError()

def login(request):
    try:
        conn = sqlite3.connect(USER_DATABASE)
        inPassword = request.values.get('password')
        email = request.values.get('username')
        query = "SELECT * FROM seeds WHERE id=" + request.values.get('id')
        cur = conn.cursor()
        cur.execute(query)
        result = cur.fetchone()
        conn.commit()
        seedStr = result[1]
        query = "DELETE FROM seeds WHERE id=" + str(result[0])
        cur.execute(query)
        query = "SELECT phoneno, pwd, failure, locked, code FROM users WHERE email='" + email + "' LIMIT 1"
        try:
            cur.execute(query)
            result = cur.fetchone()
            if result == None:
                message = "Wrong user name and password combination. Please try again."
                return createResponse(ResCode.FAILED, message)

            if result[3] == 1: # account is locked
                phoneNumber = result[0]
                maskPhoneNumber = ''
                for i in range(len(phoneNumber)-4):
                    maskPhoneNumber += 'X'
                maskPhoneNumber += "-" + phoneNumber[len(phoneNumber)-4:]
                message = "Your account is temporarily locked. A verification code was sent to your mobile phone number " + maskPhoneNumber + ". Please enter the verification code to unclock your account."
                return sendSMSMessage(conn, result[0], message)
            else:
                seed = result[1] + seedStr
                hashed = sha256(seed).hexdigest()
                if inPassword == hashed:
                    query = "UPDATE users SET failure= 0, locked= 0, code=0, codeexpiry=0 WHERE email='" + email + "'";
                    try:
                        cur.execute(query)
                        conn.commit()
                        conn.close()
                        message = "Welcome back."
                        return createResponse(ResCode.OK, message)
                    except Error as e:
                        return databaseError()
                else:
                    failure = result[2] # log attempt failure
                    # increase failure count
                    failure += 1
                    query = ""
                    if failure >= MAX_FAILURE:
                        query = "UPDATE users SET failure= 0, locked= 1 WHERE email='" + email + "'";
                    else:
                        query = "UPDATE users SET failure= " + str(failure) + " WHERE email='" + email + "'";
                    try:
                        cur.execute(query)
                        conn.commit()
                        conn.close()
                        message = "Wrong user name and password combination. Please try again."
                        return createResponse(ResCode.FAILED, message)
                    except Error as e:
                        return databaseError()
        except Exception as e:
            return databaseError()
    except Exception as e:
        return databaseError()

def resetPwd(request):
    conn = sqlite3.connect(USER_DATABASE)
    cur = conn.cursor()
    email = request.values.get('username')
    query = "SELECT phoneno, code, codeexpiry FROM users WHERE email='" + email + "' LIMIT 1";
    try:
        cur.execute(query)
        result = cur.fetchone()
        if result is None:
            message = "Account does not exist."
            return createResponse(ResCode.UNKNOWN, message)
        else:
            pwd = request.values.get('pwd')
            inPasscode = request.values.get('code')
            if pwd == None and inPasscode == None:
                phoneNumber = result[0]
                maskPhoneNumber = ''
                for i in range(len(phoneNumber)-4):
                    maskPhoneNumber += 'X'
                maskPhoneNumber += "-" + phoneNumber[len(phoneNumber)-4:]
                message = "A verification code was sent to your mobile phone number " + maskPhoneNumber + ". Please enter the verification code to reset your password."
                return sendSMSMessage(conn, result[0], message)
            else:
                timeStamp = math.floor(time.time())
                gap = timeStamp - result[2]
                if gap < 3600:
                    if inPasscode > 100000 and result[1] == int(inPasscode):
                        query = "UPDATE users SET pwd= '" + pwd + "', code=0, locked=0, failure=0, codeexpiry=0 WHERE email='" + email + "'";
                        try:
                            cur.execute(query)
                            conn.commit()
                            conn.close()
                            message = "Password changed successfully."
                            return createResponse(ResCode.OK, message)
                        except Error as e:
                            return databaseError()
                    else:
                        query = "UPDATE users SET code=0, codeexpiry=0 WHERE email='" + email + "'"
                        try:
                            cur.execute(query)
                            conn.commit()
                            conn.close()
                            message = "Invalid verification code. Click resend to get a new verification code."
                            return createResponse(ResCode.INVALID, message)
                        except Error as e:
                            return databaseError()
                else:
                    conn.close()
                    message = "Verification code expired. Click resend to get a new verification code."
                    return createResponse(ResCode.INVALID, message)
    except Error as e:
        return databaseError()

def verifyPasscode(request):
    conn = sqlite3.connect(USER_DATABASE)
    cur = conn.cursor()
    inPasscode = int(request.values.get('passcode'))
    email = request.values.get('username')
    query = "SELECT locked, code, codeexpiry FROM users WHERE email='" + email + "' LIMIT 1"
    try:
        cur.execute(query)
        result = cur.fetchone()
        if result[0] == 0:
            message = "Please login."
            return createResponse(ResCode.OK, message)
        else:
            if inPasscode != None:
                timeStamp = math.floor(time.time())
                gap = timeStamp - result[2] #codeexpiry
                if gap < 3600:
                    if inPasscode > 100000 and result[1] == inPasscode:
                        query = "UPDATE users SET failure=0, locked=0, code=0, codeexpiry=0 WHERE email='" + email + "'"
                        try:
                            cur.execute(query)
                            conn.commit()
                            conn.close()
                            message = "Please login."
                            return createResponse(ResCode.OK, message)
                        except Error as e:
                            return databaseError()
                    else:
                        query = "UPDATE users SET code=0, codeexpiry=0 WHERE email='" + email + "'"
                        try:
                            cur.execute(query)
                            conn.commit()
                            conn.close()
                            message = "Invalid verification code. Click resend to get a new verification code."
                            return createResponse(ResCode.INVALID, message)
                        except Error as e:
                            return databaseError()
                else:
                    conn.close()
                    message = "Verification code expired. Click resend to get a new verification code."
                    return createResponse(ResCode.INVALID, message)
            else:
                conn.close()
                message = "Invalid verification code."
                return createResponse(ResCode.FAILED, message)
    except Error as e:
        return databaseError()

def resendCode(request):
    conn = sqlite3.connect(USER_DATABASE)
    cur = conn.cursor()
    email = request.values.get('username')
    query = "SELECT phoneno FROM users WHERE email='" + email + "' LIMIT 1";
    try:
        cur.execute(query)
        result = cur.fetchone()
        message = "Please check your SMS for verification code to unclock your account."
        return sendSMSMessage(conn, result[0], message)
    except Error as e:
        return databaseError()

def createTable():
    try:
        conn = sqlite3.connect(USER_DATABASE)
        query = 'CREATE TABLE if not exists users (id INT AI PRIMARY KEY, phoneno VARCHAR(12) UNIQUE NOT NULL, email VARCHAR(64) UNIQUE NOT NULL, pwd VARCHAR(256) NOT NULL, fname VARCHAR(48) NOT NULL, lname VARCHAR(48) NOT NULL, failure INT DEFAULT 0, locked INT DEFAULT 0, code INT11 DEFAULT 0, codeexpiry DOUBLE DEFAULT 0)'
        cur = conn.cursor()
        cur.execute(query)
        conn.commit()
        conn.close()
    except Error as e:
        print(e)

def canLogin():
    try:
        conn = sqlite3.connect(USER_DATABASE)
        query = "SELECT * FROM users"
        cur = conn.cursor()
        result = cur.execute(query)
        conn.close()
        if result == None:
            #createTable()
            return False
        else:
            return True
    except Error as e:
        return False

def signup(request):
    createTable()
    try:
        phoneno = request.values.get('phoneno')
        email = request.values.get('email')
        password = request.values.get('password')
        fname = request.values.get('fname')
        lname = request.values.get('lname')
        conn = sqlite3.connect(USER_DATABASE)
        valStr = "NULL,'" + phoneno + "',"
        valStr += "'" + email + "',"
        valStr += "'" + password + "',"
        valStr += "'" + fname + "',"
        valStr += "'" + lname + "',0,0,0,0"
        query = "INSERT INTO users VALUES ("+ valStr +")"
        cur = conn.cursor()
        cur.execute(query)
        conn.commit()
        conn.close()
        message = "Congratulations."
        return createResponse(ResCode.OK, message)
    except Error as e:
        return databaseError()

def sendSMSMessage(conn, toNumber, message):
    if os.environ.get("ENVIRONMENT_MODE") == "sandbox":
        rcsdk = SDK(os.environ.get("CLIENT_ID_SB"), os.environ.get("CLIENT_SECRET_SB"), 'https://platform.devtest.ringcentral.com')
        username = os.environ.get("USERNAME_SB")
        pwd = os.environ.get("PASSWORD_SB")
    else:
        rcsdk = SDK(os.environ.get("CLIENT_ID_PROD"), os.environ.get("CLIENT_SECRET_PROD"), 'https://platform.ringcentral.com')
        username = os.environ.get("USERNAME_PROD")
        pwd = os.environ.get("PASSWORD_PROD")
    platform = rcsdk.platform()
    try:
        platform.login(username, '', pwd)
        code = str(generateRandomCode(6))
        params = {
            'from': {'phoneNumber': username},
            'to': [{'phoneNumber': toNumber}],
            'text': "Your verification code is " + code
            }
        response = platform.post('/account/~/extension/~/sms', params)
        try:
            ts = time.time()
            timeStamp = str(math.floor(ts))
            query = "UPDATE users SET code= " + code + ", codeexpiry= " + timeStamp + " WHERE phoneno='" + toNumber + "'";
            cur = conn.cursor()
            cur.execute(query)
            conn.commit()
            conn.close()
            error = ResCode.LOCKED
            return createResponse(error, message)
        except Error as e:
            conn.close()
            return databaseError()
    except Exception as e:
        conn.close()
        error = ResCode.UNKNOWN
        message = "Cannot send verification code. Please click the Resend button to try again."
        return createResponse(error, message)

def generateRandomCode(digits):
    range_start = 10**(digits-1)
    range_end = (10**digits)-1
    return randint(range_start, range_end)

def createResponse(error, message):
    response = {
        'error': error,
        'message': message
    }
    return json.dumps(response)

def databaseError():
    response = {
        'error': ResCode.UNKNOWN,
        'message': "User database error. Please try again."
    }
    return json.dumps(response)
