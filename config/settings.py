"""Central settings and configuration for Mechatronics Search Engine."""

import os
from pathlib import Path

# Base Paths
#
# Paths are derived from this file's location, not the working directory, so the
# app behaves the same when started by Streamlit Community Cloud or by hand.
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# The verified corpus lives in data/seeds_check.db (4 crawled pages, all HTTP 200).
# data/pages.db is a 0-byte leftover from an early crawl attempt and contains no
# `pages` table, so using it as the default made the indexer fail with
# "no such table: pages". All code that resolves a default database goes through
# this value; pass --db explicitly to index a different database.
DB_PATH = DATA_DIR / "seeds_check.db"
INDEX_DIR = DATA_DIR / "whoosh_index"

# Crawler Identity & Safety
USER_AGENT = "MechatronicsUniversityBot/1.0 (+https://github.com/academic-search-project; student-project@university.edu)"
REQUEST_TIMEOUT = 5.0  # seconds
DEFAULT_CRAWL_DELAY = 2.0  # seconds (used if robots.txt does not specify a delay)
MAX_CRAWL_DEPTH = 3
MAX_PAGES_TO_CRAWL = 200
MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB size ceiling to prevent memory issues

# Allowed Domains (strict allowlist)
#
# Every domain below was checked by fetching its /robots.txt with the crawler's
# own User-Agent before it was added:
#
#   docs.arduino.cc        Allow: /                       (Arduino documentation)
#   eng.libretexts.org     Allow, with "Crawl-delay: 5"    (LibreTexts engineering)
#   ocw.mit.edu            Allow: /                       (MIT OpenCourseWare)
#   howtomechatronics.com  Disallow: (empty) = allow all   (tutorials, projects)
#   en.wikibooks.org       Allow, except /w/, /api/ and /wiki/Special:*
#
# MathWorks (www.mathworks.com/help/) was evaluated and is NOT allowlisted: its
# /robots.txt returns HTTP 403 and the help pages themselves return 403 to this
# User-Agent. PolitenessManager fails closed on a 403, so no MathWorks page can
# be crawled. See the README for the permitted alternatives that were used.
ALLOWED_DOMAINS = [
    "docs.arduino.cc",
    "eng.libretexts.org",
    "ocw.mit.edu",
    "howtomechatronics.com",
    "en.wikibooks.org",
]

# Curated, hand-verified seed URLs (every one fetched with HTTP 200 and parsed to
# non-empty text before being added). They span the six topics the UI filters:
# Robotics, Control Systems, Electronics, Mechanical Engineering, Sensors and
# Embedded Systems.
#
# Curation notes, because they drive the crawl:
#
# * docs.arduino.cc publishes most of /learn/ as a client-rendered shell: 15 of 19
#   tested /learn/ subpages (stepper-motors, transistor-motor-control, spi, ...)
#   return HTTP 200 but contain no server-rendered text, so the indexer would skip
#   them. Only /learn/, /hardware/ and the hardware product pages carry real text,
#   so those are the seeds used here.
# * The two original 4-page corpus seeds (/learn/, /hardware/,
#   /Bookshelves/Mechanical_Engineering, /Bookshelves/Electrical_Engineering) are
#   kept so the pre-existing documents remain part of the collection.
# * Wikibooks "Print_version", "All_Versions" and "All_pages" pages are omitted on
#   purpose: each duplicates an entire book in one document.
SEED_URLS = [
    # --- Embedded Systems / Electronics (docs.arduino.cc) ---
    "https://docs.arduino.cc/learn/",
    "https://docs.arduino.cc/hardware/",
    "https://docs.arduino.cc/hardware/engineering-kit-motors-backup/",
    "https://docs.arduino.cc/hardware/mkr-motor-carrier-lite/",
    "https://docs.arduino.cc/hardware/plc-starter-kit/",
    "https://docs.arduino.cc/hardware/opta-lite/",
    "https://docs.arduino.cc/hardware/sensor-kit/",
    "https://docs.arduino.cc/hardware/automation-bot-bundle/",
    "https://docs.arduino.cc/hardware/explore-iot-kit/",
    "https://docs.arduino.cc/hardware/science-kit/",
    # --- Mechanical Engineering / Robotics / Control (eng.libretexts.org) ---
    "https://eng.libretexts.org/Bookshelves/Mechanical_Engineering",
    "https://eng.libretexts.org/Bookshelves/Electrical_Engineering",
    "https://eng.libretexts.org/Bookshelves/Mechanical_Engineering/Introduction_to_Autonomous_Robots_(Correll)",
    "https://eng.libretexts.org/Bookshelves/Industrial_and_Systems_Engineering/Introduction_to_Control_Systems_(Iqbal)",
    "https://eng.libretexts.org/Bookshelves/Industrial_and_Systems_Engineering/Book%3A_Dynamic_Systems_and_Control_(Dahleh_Dahleh_and_Verghese)",
    "https://eng.libretexts.org/Bookshelves/Electrical_Engineering/Electronics",
    "https://eng.libretexts.org/Bookshelves/Electrical_Engineering/Introductory_Electrical_Engineering",
    "https://eng.libretexts.org/Bookshelves/Electrical_Engineering/Signal_Processing_and_Modeling",
    "https://eng.libretexts.org/Courses/University_of_Arkansas_Little_Rock/Introduction_to_Control_Systems_(Iqbal)/01%3A_Mathematical_Models_of_Physical_Systems/1.07%3A_DC_Motor_Model",
    "https://eng.libretexts.org/Bookshelves/Mechanical_Engineering/Mechanics_Map_(Moore_et_al.)",
    "https://eng.libretexts.org/Bookshelves/Mechanical_Engineering/Engineering_Mechanics_-_Statics_(Osgood_Cameron_and_Christensen)",
    "https://eng.libretexts.org/Bookshelves/Mechanical_Engineering/Mechanics_of_Materials_(Roylance)",
    # --- Control Systems / Robotics / Electronics (ocw.mit.edu) ---
    "https://ocw.mit.edu/courses/2-737-mechatronics-fall-2014/",
    "https://ocw.mit.edu/courses/16-06-principles-of-automatic-control-fall-2012/",
    "https://ocw.mit.edu/courses/16-30-feedback-control-systems-fall-2010/",
    "https://ocw.mit.edu/courses/2-12-introduction-to-robotics-fall-2005/",
    "https://ocw.mit.edu/courses/6-4210-robotic-manipulation-fall-2022/",
    "https://ocw.mit.edu/courses/2-003j-dynamics-and-control-i-fall-2007/",
    "https://ocw.mit.edu/courses/2-004-systems-modeling-and-control-ii-fall-2007/",
    "https://ocw.mit.edu/courses/2-017j-design-of-electromechanical-robotic-systems-fall-2009/",
    "https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/",
    "https://ocw.mit.edu/courses/6-071j-introduction-to-electronics-signals-and-measurement-spring-2006/",
    "https://ocw.mit.edu/courses/6-334-power-electronics-spring-2007/",
    "https://ocw.mit.edu/courses/6-101-introductory-analog-electronics-laboratory-spring-2007/",
    # --- Applied motor control, sensors, actuators (howtomechatronics.com) ---
    "https://howtomechatronics.com/tutorials/arduino/stepper-motors-and-arduino-the-ultimate-guide/",
    "https://howtomechatronics.com/tutorials/arduino/arduino-dc-motor-control-tutorial-l298n-pwm-h-bridge/",
    "https://howtomechatronics.com/tutorials/arduino/how-to-control-stepper-motor-with-a4988-driver-and-arduino/",
    "https://howtomechatronics.com/tutorials/arduino/rotary-encoder-works-use-arduino/",
    "https://howtomechatronics.com/how-it-works/electrical-engineering/stepper-motor/",
    "https://howtomechatronics.com/tutorials/arduino/ultrasonic-sensor-hc-sr04/",
    "https://howtomechatronics.com/tutorials/arduino/arduino-and-mpu6050-accelerometer-and-gyroscope-tutorial/",
    "https://howtomechatronics.com/tutorials/arduino/how-to-track-orientation-with-arduino-and-adxl345-accelerometer/",
    "https://howtomechatronics.com/how-it-works/how-planetary-gears-work-3d-printed-planetary-gearbox-design-and-test/",
    "https://howtomechatronics.com/how-it-works/electrical-engineering/mems-accelerometer-gyrocope-magnetometer-arduino/",
    "https://howtomechatronics.com/how-it-works/electrical-engineering/hall-effect-hall-effect-sensors-work/",
    "https://howtomechatronics.com/projects/arduino-robot-arm-and-mecanum-wheels-platform-automatic-operation/",
    "https://howtomechatronics.com/tutorials/arduino/diy-arduino-robot-arm-with-smartphone-control/",
    "https://howtomechatronics.com/projects/arduino-mecanum-wheels-robot/",
    "https://howtomechatronics.com/how-it-works/what-is-cycloidal-driver-designing-3d-printing-and-testing/",
    # --- Control theory, robotics and electronics textbooks (en.wikibooks.org) ---
    "https://en.wikibooks.org/wiki/Control_Systems",
    "https://en.wikibooks.org/wiki/Robotics",
    "https://en.wikibooks.org/wiki/Embedded_Systems",
    "https://en.wikibooks.org/wiki/Electronics",
    "https://en.wikibooks.org/wiki/Control_Systems/Introduction",
    "https://en.wikibooks.org/wiki/Control_Systems/System_Modeling",
    "https://en.wikibooks.org/wiki/Control_Systems/Transfer_Functions",
    "https://en.wikibooks.org/wiki/Control_Systems/Feedback_Loops",
    "https://en.wikibooks.org/wiki/Control_Systems/Controllers_and_Compensators",
    "https://en.wikibooks.org/wiki/Control_Systems/Bode_Plots",
    "https://en.wikibooks.org/wiki/Control_Systems/Root_Locus",
    "https://en.wikibooks.org/wiki/Control_Systems/State-Space_Equations",
    "https://en.wikibooks.org/wiki/Embedded_Systems/Embedded_Systems_Introduction",
    "https://en.wikibooks.org/wiki/Embedded_Systems/Microprocessor_Introduction",
    "https://en.wikibooks.org/wiki/Robotics/Design_Basics/What_you_should_know",
    "https://en.wikibooks.org/wiki/Electronics/Voltage,_Current,_and_Power",
]

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)
