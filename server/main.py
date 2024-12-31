import requests
from flask import Flask, render_template, request, g, jsonify, redirect, url_for
import sqlite3
from miio import Device
import asyncio
import statistics
from statsmodels.tsa.arima.model import ARIMA

# requirements: instalat miio (-> doc oficiala), flask, 'flask[async]', statsmodel

app = Flask(__name__)
DATABASE = 'database.db'

# informatii despre bec
ip = ""
token = ""
dev = None

# informatii despre bot-ul de Telegram
bot_token = ""
chat_id = ""


def send_telegram_message(message):
    global bot_token, chat_id
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, json=payload)
        response.close()
        print("Message sent successfully!")
    except Exception as e:
        print(f"Error sending message: {e}")


def isLoggedIn():
    if ip == "" or token == "":
        return False
    return True


def updateBrightness(bright):
    global dev

    res = ""
    err = False

    try:
        res = dev.send("get_prop", ["power"])
        status = res[0]

        if status != "on":
            res = "Error: the lightbulb has to be turned on first :("
            err = True
            return err, res
    except Exception as e:
        err = True
        res = "Error: the operation could not be done, please try again :("

    try:
        res = dev.send("set_bright", [bright])
    except Exception as e:
        err = True
        res = "Error: the operation could not be done, please try again :("

    if not err:
        res = "The lightbulb has now the brightness value of " + str(bright)

    return err, res


@app.route("/login", methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        data = request.form

        global ip, token, dev, bot_token, chat_id
        ip = data['ip']
        token = data['token']
        bot_token = data['bot_token']
        chat_id = data['chat_id']
        dev = Device(ip, token, timeout=10)

        return redirect(url_for('home'))

    return render_template("login.html")


def getDB():
    db = getattr(g, '_database', None)

    if db is None:
        db = g._database = sqlite3.connect(DATABASE)

    return db


def initDB():
    with app.app_context():
        db = getDB()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())

        db.commit()


def addEntry(state, light_val, light_int, color_temp):
    with app.app_context():
        db = getDB()

        db.execute('INSERT INTO entries (state, light_val, light_intensity, color_temp) VALUES (?, ?, ?, ?)',
                   [state, light_val, light_int, color_temp])
        db.commit()
        return jsonify({'status': 'Entry added'})


@app.route("/getDBData")
def showEntries():
    with app.app_context():
        db = getDB()

        cur = db.execute('SELECT id, record_time, state, light_val, light_intensity, color_temp FROM entries')

        entries = cur.fetchall()
        return jsonify(entries)


@app.route("/getStatistics")
def showStatistics():
    with app.app_context():
        global bot_token, chat_id

        mean = ""
        res = ""
        difvals = ""

        db = getDB()

        cur = db.execute('SELECT light_intensity FROM entries')

        entries = cur.fetchall()

        if len(entries) < 2:
            return render_template("statistics.html", res=res, mean=mean, difvals=difvals)

        vals = [x[0] for x in entries]

        model = ARIMA(vals, order=(5, 1, 0))
        model_fit = model.fit()
        output = model_fit.forecast()
        res = "The next value of the light intensity should be " + str(output[0])
        mean = "The mean value of all the registered intensities is " + str(statistics.fmean(vals))
        difvals = "The different values of all registered intensities are " + str(statistics.multimode(vals))

        if bot_token != "" and chat_id != "":
            send_telegram_message(res)
            send_telegram_message(mean)
            send_telegram_message(difvals)

        if res == "" or mean == "" or difvals == "":
            res = "The number of entries in the database is to small to determine statistics :("

        return render_template("statistics.html", res=res, mean=mean, difvals=difvals)


@app.route("/adjust-brightness")
def adjustBrightness():
    global dev

    res = ""
    bright = 1

    try:
        bright = int(dev.send("get_prop", ["bright"])[0])
    except Exception as e:
        err = True
        res = "Error: the lightbulb is not connected, please try again :("

        return redirect(url_for('brightResult', bright=bright, err=True, res=res))

    with app.app_context():
        db = getDB()

        cur = db.execute('SELECT * FROM entries ORDER BY record_time DESC LIMIT 1')
        latest_entry = cur.fetchone()

        if not latest_entry:
            res = "The database has no entries, the brightness cannot be adjusted :("
            err = True

            return redirect(url_for('brightResult', bright=bright, err=err, res=res))

    light_int = latest_entry[4]

    if light_int <= 10:
        bright = 100

    if 10 < light_int <= 40:
        bright = 75

    if 40 < light_int <= 80:
        bright = 50

    if light_int > 80:
        bright = 25

    err, res = updateBrightness(bright)

    return redirect(url_for('brightResult', bright=bright, err=err, res=res))


@app.route("/visualizeData")
def showGraph():
    return render_template("visualize_data.html")


@app.route("/twinkle")
async def twinkle():
    for _ in range(0, 3):
        turnOn()
        await asyncio.sleep(0.5)
        updateBrightness(100)
        await asyncio.sleep(0.5)
        turnOff()
        await asyncio.sleep(0.5)

    return render_template("twinkle.html")


# date primite de la ESP32 prin Wi-Fi
@app.route('/submit', methods=['POST'])
def submitData():
    try:
        data = request.get_json()

        global dev

        try:
            info = dev.send("get_prop", ["power", "bright", "ct"])
        except Exception as e:
            return jsonify({"error": "Missing some data"}), 400

        state = info[0]
        light_val = int(info[1])

        # bec-ul meu e prea vechi si nu ii pot afla programatic temperatura culorii; 2700 e valoarea din specificatii
        # color_temp = int(info[2])
        color_temp = 2700

        light_int = data.get("light_intensity")

        if light_int is None:
            return jsonify({"error": "Missing some data"}), 400

        db = getDB()

        addEntry(state, light_val, light_int, color_temp)
        db.commit()

        return jsonify({"message": "Data added successfully"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    if isLoggedIn():
        return render_template("home.html")
    return redirect(url_for('login'))


@app.route("/turn-on")
def turnOn():
    global dev

    res = ""
    err = False

    try:
        res = dev.send("set_power", ["on"])
    except Exception as e:
        err = True
        res = "Error: the lightbulb is not connected, please try again :("

    return render_template("turn_on.html", err=err, res=res)


@app.route("/set-brightness", methods=('GET', 'POST'))
def setBrightness():
    if request.method == 'POST':
        data = request.form

        bright = int(data['brightness'])

        err, res = updateBrightness(bright)

        return redirect(url_for('brightResult', bright=bright, err=err, res=res))

    return render_template("set_brightness.html")


@app.route("/set-brightness-result/<bright>/<err>/<res>")
def brightResult(bright, err, res):
    return render_template("set_brightness_result.html", bright=bright, err=err, res=res)


@app.route("/turn-off")
def turnOff():
    global dev

    res = ""
    err = False

    try:
        res = dev.send("set_power", ["off"])
    except Exception as e:
        err = True
        res = "Error: the lightbulb is not connected, please try again :("

    return render_template("turn_off.html", err=err, res=res)


@app.route("/current-status")
def currentStatus():
    global dev

    res = ""
    err = False
    power = ""
    bright = ""
    ct = ""

    try:
        res = dev.send("get_prop", ["power", "bright", "ct"])
        power = res[0]
        bright = res[1]
        ct = res[2]
    except Exception as e:
        err = True
        res = "Error: the lightbulb is not connected, please try again :("

    return render_template("current_status.html", err=err, res=res, power=power, bright=bright, ct=ct)


if __name__ == "__main__":
    initDB()
    app.run(ssl_context=('cert.pem', 'key.pem'), debug=True, host='0.0.0.0', port=5000)
