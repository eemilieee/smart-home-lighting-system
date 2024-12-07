from flask import Flask, render_template, request, g, jsonify, redirect, url_for
import sqlite3
from miio import Device
import asyncio

# requirements: instalat miio (-> doc oficiala), flask, 'flask[async]'

app = Flask(__name__)
DATABASE = 'database.db'

# informatii despre bec
ip = ""
token = ""
dev = None


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

        global ip, token, dev
        ip = data['ip']
        token = data['token']
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

        # becul meu e prea vechi si nu ii pot afla programatic temperatura culorii; 2700 e valoarea din specificatii
        # color_temp = int(info[2])
        color_temp = 2700

        light_int = data.get('light_intensity')

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
    app.run(debug=True, host='0.0.0.0', port=5000)
