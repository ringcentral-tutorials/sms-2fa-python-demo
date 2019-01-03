import router
from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/')
@app.route('/index')
def index():
    if router.canLogin() is True:
        return render_template('index.html', title='Home')
    else:
        return render_template('signup.html', title='Signup')

@app.route('/about')
def about():
    return render_template('about.html', title='About')

@app.route('/getseed', methods=['GET'])
def getSeed():
  return router.getSeed()

@app.route('/login', methods=['POST'])
def calllogin():
    return router.login(request)

@app.route('/resetpwd', methods=['POST'])
def resetPwd():
    return router.resetPwd(request)

@app.route('/verifypasscode', methods=['POST'])
def verifyPasscode():
   return router.verifyPasscode(request)

@app.route('/resendcode', methods=['POST'])
def resendCode():
   return router.resendCode(request)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        router.createTable()
        return render_template('signup.html', title='Signup')
    else:
        return router.signup(request)
