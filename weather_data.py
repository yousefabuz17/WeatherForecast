import json
import os
import socket
import sys
from base64 import b64encode
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import requests
from bs4 import BeautifulSoup
from geocoder import ip
from rapidfuzz import fuzz, process

from emojis import simple_weather_emojis as e
from weather_db_connect import ForecastDB

WIND_DIRECTIONS = {
    'N': 'North',
    'S': 'South',
    'E': 'East',
    'W': 'West',
    'NE': 'Northeast',
    'NW': 'Northwest',
    'SE': 'Southeast',
    'SW': 'Southwest',
    'NNE': 'North-northeast',
    'NNW': 'North-northwest',
    'ENE': 'East-northeast',
    'ESE': 'East-southeast',
    'SSE': 'South-southeast',
    'SSW': 'South-southwest',
    'WSW': 'West-southwest',
    'WNW': 'West-northwest',
}

class ConfigInfo(NamedTuple):
    weather_api: str
    forecast_api: str
    geo_api: str
    host: str
    database: str
    username: str
    password: str

class LocationInfo(NamedTuple):
    arg1: float=None
    arg2: float=None

class HourlyData(NamedTuple):
    date: str
    time: str
    temp: str

@dataclass
class ConditionInfo:
    icon_code: str
    description: str

@dataclass
class ParsedDate:
    year: str
    month: str
    day: str


@dataclass
class Args:
    arg1: str=None
    arg2: str=None
    arg3: str=None

class SimpleWeather: #! Turn into a simple GUI
    def __init__(self, place=None):
        self.place = place
        self.current_location = self.get_location()
        self.base_url = 'http://api.weatherapi.com/v1/current.json'
        self.query_params = {'key': config.weather_api, 'q': self.place or self.get_location()}

    @staticmethod
    def get_ip_address():
        try:
            ip_address = ip('me').ip
            return ip_address
        
        except socket.error as e:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip_address = s.getsockname()[0]
            return ip_address
        
        except Exception as e:
            print("Error: Failed to fetch IP address.", e)
            return None
            

    def get_location(self):
        try:
            ip_address = self.get_ip_address
            response = requests.get('https://ipinfo.io/', params={
                'token': config.geo_api,
                'ip': ip_address,
                'contentType': 'json'
            }).json()
            city = response.get('city')
            region = response.get('region')
            return city or region or 'Unknown'
        except requests.RequestException as e:
            print("Error: Failed to fetch location data.", e)
            raise SystemExit

    def get_weather(self):
        try:
            response = requests.get(self.base_url, params=self.query_params)
            response.raise_for_status()
        except requests.RequestException as e:
            print("Error: Failed to fetch weather data.", e)
            raise SystemExit

        if response.status_code == 429:
            print("Error: Too many requests. Please try again later.")
            return self.get_weather()
        return response.json()

    def get_weather_data(self):
        """
        Extract the relevant weather data from the API response.

        Returns:
            - `tuple`: A tuple containing the weather data.
        """
        data = self.get_weather()
        if not data:
            return None
        
        name = data['location']['name']
        unparsed_date = data['current']['last_updated'].split()[0].split('-')

        def parse_date(date_str: str):
            """
            Parse the date string into separate year, month, and day components.

            Returns:
                - `ParsedDate`: A named tuple containing the year, month, and day components.
            """

            try: year, month, day = date_str.split('-')
            except (ValueError, AttributeError): year, month, day = '-'.join(date_str).split('-')
            
            return ParsedDate(year, month, day)

        date_ = parse_date(unparsed_date)
        date = f'{date_.month}/{date_.day}/{date_.year}'
        condition = data['current']['condition']['text']
        f_degrees = data['current']['temp_f']
        feels_like = data['current']['feelslike_f']
        wind_mph = data['current']['wind_mph']
        wind_dir = data['current']['wind_dir']
        humidity = data['current']['humidity']
        get_weather_emoji = lambda condition: e.get(condition, '')

        return (
            name,
            date,
            condition,
            f_degrees,
            feels_like,
            wind_mph,
            wind_dir,
            humidity,
            get_weather_emoji(condition)
        )

    def display_weather_report(self):
        """
        Display the weather report.
        """
        weather_data = self.get_weather_data()
        
        if not weather_data:
            print('No data for this location found.')
            return
        
        name, date, condition, f_degrees, feels_like, wind_mph, wind_dir, humidity, emoji = weather_data
        print(
            f'''\n \033[4;5;36;1mWeather Report for {name}\033[0m       \033[1;2m[Last Updated: {date}]\033[0m\n
            \033[1;31mTemperature:\033[0m {f_degrees}°F, but feels like {feels_like}°F
            \033[1;31mWind Speed:\033[0m {wind_mph} mph
            \033[1;31mWind Direction:\033[0m {wind_dir} ({WIND_DIRECTIONS.get(wind_dir, '')})
            \033[1;31mWeather Condition:\033[0m {condition} {emoji}
            \033[1;31mHumidity:\033[0m {humidity}%
            ''')
    
    @staticmethod
    def dump_json(data, file_name=None):
        """
        Dump the data into a JSON file.

        Parameters:
            - `data` (list): The data to be dumped into the JSON file.
        """
        json_file = Path(__file__).parent.absolute() / 'data_files' / file_name
        if os.path.isfile(json_file) or not os.path.isfile(json_file):
            try:
                if file_name:
                    if not file_name.endswith('.json'):
                        with open(f'{json_file}.json', 'w') as f:
                            json.dump(data, f, indent=2)
                    else:
                        with open(json_file, 'w') as f:
                            json.dump(data, f, indent=2)
            except OSError as e:
                print("Error: Failed to write JSON data.", e)
                raise SystemExit

class WeatherForecast(SimpleWeather):
    def __init__(self, place=None):
        """
        Initialize the WeatherForecast class.

        Parameters:
            - `place` (str, optional): The location for which to retrieve weather information. Defaults to None.
        """
        super().__init__(place)
        self.base_url = 'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline'
        self.query_params = {
            'key': config.forecast_api,
            'contentType': 'json',
            'unitGroup': 'metric',
            'location': self.place or self.get_location(),
        }
    
    @staticmethod
    def get_config():
        return json.load(open(Path(__file__).parent.absolute() / 'config.json', encoding='utf-8'))
    
    
    def get_coordinates(self):
        data = self.get_weather()
        if not data:
            return None
        return LocationInfo(arg1=data['longitude'], arg2=data['latitude'])
    
    def get_weather(self):
        """
        Retrieve the weather data for the forecast.

        Returns:
            - `dict`: The JSON response containing the weather data.
        """
        try:
            response = requests.get(self.base_url, params=self.query_params)
            response.raise_for_status()
            if response.status_code == 429:
                print("Error: Too many requests. Please try again later.")
                return None
            return response.json()
        except requests.RequestException as e:
            print("Error: Failed to fetch weather data.", e)
            raise SystemExit

    def full_weather_data(self):
        """
        Extract the full weather data for the forecast.

        Returns:
            - `list`: A list containing the full weather data.
        """
        data = self.get_weather()
        if not data:
            data = []
        full_data = []
        
        coordinates = LocationInfo(arg1=data['longitude'], arg2=data['latitude'])
        location_name = data['resolvedAddress']
        both_degrees = lambda c_temp: (c_temp, round((c_temp * 9 / 5) + 32, 2))  # (Celsius, Fahrenheit)
        
        min_temp = [LocationInfo(*both_degrees(data['days'][i]['tempmin'])) for i in range(min(15, len(data['days'])))]
        max_temp = [LocationInfo(*both_degrees(data['days'][i]['tempmax'])) for i in range(min(15, len(data['days'])))]
        
        for i in range(min(15, len(data['days']))):
            day_data = data['days'][i]
            date_ = ParsedDate(*day_data['datetime'].split('-'))
            date = f'{date_.month}/{date_.day}/{date_.year}'
            hours = [day_data['hours'][idx]['datetime'] for idx in range(24)]
            humidity = [round(day_data['hours'][idx]['humidity']) for idx in range(24)]
            conditions = [[day_data['hours'][idx]['conditions'], ''] for idx in range(24)]
            hourly_temp = [LocationInfo(*both_degrees(day_data['hours'][idx]['temp'])) for idx in range(24)]
            all_data = zip(hours, hourly_temp, humidity, conditions)
            day_full_data = list(all_data)
            full_data.append((location_name, coordinates, date, min_temp, max_temp, day_full_data))
        return full_data

    def data_to_json(self, data=None):
        data = self.full_weather_data() if not data else data
        clean_data = []
        conditions = set()
        for _, element in enumerate(data):
            item = {
                'location': element[0],
                'coordinates': {'longitude': element[1].arg1,
                                'latitude': element[1].arg2},
                
                'day': {'date': element[2],
                        'min_temp': {'Celcius':element[3][_].arg1,
                                    'Fahrenheit':element[3][_].arg2},
                        'max_temp': {'Celcius':element[4][_].arg1,
                                    'Fahrenheit':element[4][_].arg2}}
                        }
            hourly_data = []
            for i in element[5]:
                conditions.add(i[3][0])
                hourly_item = {
                    'hour': i[0],
                    'temperature': {'Celcius': i[1].arg1,
                                    'Fahrenheit':i[1].arg2},
                    'humidity': i[2],
                    'conditions': i[3][0],
                    'emoji': '' 
                }
                hourly_data.append(hourly_item)
            item['day']['hourly_data'] = hourly_data
            clean_data.append(item)
        try:
            SimpleWeather.dump_json(clean_data, file_name='Forecast_data.json')
        except OSError as e:
            print("Error: Failed to write JSON data.", e)
            raise SystemExit
        clean_data = WeatherConditons.modify_condition(clean_data)
        return clean_data

class HistoricalData:
    def __init__(self):
        self.coordinates = WeatherForecast().get_coordinates()
        self.base_url = 'https://archive-api.open-meteo.com/v1/archive?'\
                        f'latitude={self.coordinates.arg2}&longitude={self.coordinates.arg1}&'\
                        'start_date=2020-12-31&end_date=2023-07-01&'\
                        'hourly=temperature_2m&temperature_unit=fahrenheit&'\
                        'windspeed_unit=mph'

    def parse_history(self):
        try:
            response = requests.get(self.base_url)
            response.raise_for_status()
        except requests.RequestException as e:
            print("Error: Failed to fetch weather data.", e)
            raise SystemExit

        if response.status_code == 429:
            print("Error: Too many requests. Please try again later.")
        return response.json()
    
    def get_history_data(self):
        data = self.parse_history()
        
        if not data:
            return None
        
        data = data['hourly']
        hourly_temp = data['temperature_2m']
        date_and_time = [i.split('T') for i in data['time']]
        modified_time = [[i[0], f'{i[1]}:00'] for i in date_and_time]
        data_zipped = list(zip(hourly_temp, modified_time))
        full_data = [HourlyData(date=i[1][0],time=i[1][-1],temp=i[0]) for i in data_zipped]
        return full_data
    
    def hourly_json(self, data):
        json_hourly = OrderedDict()
        for idx, item in enumerate(data, start=1):
            date_key = f'Date: {item.date}'
            if date_key not in json_hourly:
                json_hourly[date_key] = OrderedDict()
            json_hourly[date_key][f'Time {idx}'] = item.time
            json_hourly[date_key][f'Temperature {idx}'] = item.temp
        
        SimpleWeather.dump_json(json_hourly, file_name='History_data')
        
        return json_hourly

class WeatherConditons:
    def __init__(self):
        self.scrape_url = 'https://openweathermap.org/weather-conditions'

    def scrape_data(self):
        """
        Scrape the weather conditions data from the website.

        Returns:
            - `list`: A list containing the scraped weather conditions data.
        """
        try:
            response = requests.get(self.scrape_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            tables = soup.find('table', class_='table')

            data = []
            for icon_table in tables.find_all('tr'):
                cells = icon_table.find_all("td")
                if len(cells) >= 3:
                    for _, _ in enumerate(cells):
                        icon_code = cells[0].text.strip()[:3]
                        description = cells[-1].text.strip().title()
                    data.append(ConditionInfo(icon_code=icon_code, description=description))
            return data
        except requests.RequestException as e:
            print("Error: Failed to fetch weather conditions data.", e)
            raise SystemExit
    
    @staticmethod
    def modify_condition(data, condition=None):
        """
        Modify the weather conditions in the data based on the scraped weather conditions.

        This method compares the weather conditions obtained from the API with the scraped weather conditions 
        to find the best matching condition. It uses fuzzy string matching to identify the best correlated match 
        between the two condition sets. The weather conditions in the data are updated with the best matching 
        condition, and the corresponding emoji is also modified accordingly.

        Parameters:
            - `data` (list): The weather data to be modified.
            - `condition` (str, optional): The specific condition to modify. Defaults to None.
        """
        global emoji_con, missing_codes
        
        weather_conditions = WeatherConditons().scrape_data()
        unpacked = list(map(lambda i: [i.icon_code, i.description], weather_conditions))
        emoji_con = {}
        for item in data:
            hourly_data = item['day']['hourly_data']
            for conditions in hourly_data:
                condition = conditions['conditions']
                best_match_ = process.extractOne(condition.lower(), list(map(lambda i: i.description, weather_conditions)), scorer=fuzz.ratio)
                best_match = best_match_[0] if best_match_ else ""
                conditions['conditions'] = best_match
                conditions['emoji'] = list(filter(lambda i: i[0] if i[1]==best_match else '', unpacked))[0][0] # [['03d', 'Scattered Clouds']] --> '03d' --> b'PNG' (after using modify_emoji)
                emoji_con[conditions['conditions']] = conditions['emoji']
        missing_codes = {desc: icon for icon,desc in unpacked if icon not in emoji_con.values()}
        try:
            SimpleWeather.dump_json(data, file_name='Forecast_data.json')
        except OSError as e:
            print("Error: Failed to write JSON data.", e)
            raise SystemExit
        finally:
            emoji_con = OrderedDict(sorted(emoji_con.items()))
            WeatherIcons.modify_icons()
        return

class WeatherIcons:
    def __init__(self):
        self.base_url = 'https://openweathermap.org/img/wn/{}@2x.png'
    
    def parse_icon_url(self, icon_code):
        try:
            response = requests.get(self.base_url.format(icon_code))
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            print("Error: Failed to fetch icon data.", e)
            raise SystemExit

    @staticmethod
    def modify_icons():
        data = json.loads((Path(__file__).parent.absolute() / 'data_files' / 'Forecast_data.json').read_text())
        path = Path(__file__).parent.absolute()
        weather_icons = WeatherIcons()
        all_codes = OrderedDict(sorted(emoji_con.items() | missing_codes.items(), key=lambda i: i[1]))

        for _, icon_code in emoji_con.items():
            png_bytes = weather_icons.parse_icon_url(icon_code)
            for item in data:
                hourly_data = item['day']['hourly_data']
                for conditions in hourly_data:
                    if emoji_con.get(conditions['conditions']) == icon_code:
                        conditions['emoji'] = {'Description': conditions['conditions'],
                                                'Icon Code':icon_code,
                                                'Decoded Bytes':b64encode(png_bytes).decode('utf-8')}
                                                # encode back for bytes
                    else:
                        pass
        
        full_modifications = {}
        for condition, code in all_codes.items():
            with open(path / 'icons' / f'{code}_day.png', 'wb') as day_file_:
                with open(path / 'icons' / f'{code}_night.png', 'wb') as night_file_:
                    day_bytes = weather_icons.parse_icon_url(code)
                    night_bytes = weather_icons.parse_icon_url(code.replace('d', 'n'))
                    day_file_.write(day_bytes)
                    night_file_.write(night_bytes)
                    full_modifications[condition] = {'Description': condition,
                                                'Icon Code':code,
                                                'Day Decoded Bytes':b64encode(day_bytes).decode('utf-8'),
                                                'Night Decoded Bytes':b64encode(night_bytes).decode('utf-8')}
        try:
            SimpleWeather.dump_json(data, file_name='Forecast_data.json')
            SimpleWeather.dump_json(full_modifications, file_name='weather_conditions')
        except OSError as e:
            print("Error: Failed to write JSON data.", e)
            raise SystemExit
        return full_modifications


def main():
    global config
    
    config = ConfigInfo(*WeatherForecast.get_config().values())
    
    def get_forecast(place):
        forecast = WeatherForecast(place)
        forecast.full_weather_data()
        forecast.data_to_json() # Full JSON forecast data
        sql_params = map(lambda i: getattr(config, i), ['host', 'database', 'username', 'password'])
        ForecastDB(sql_params)
    
    def get_history():
        history = HistoricalData()
        hist_data = history.get_history_data()
        history.hourly_json(hist_data)

    try:
        simple_weather = input("\nWould you like a simple weather report? (y/n): ").lower()
        place = input("Enter a location (leave empty for current location): ")
        if simple_weather in ['no', 'n']:
            get_forecast(place)
            get_history()
        else:
            SimpleWeather(place).display_weather_report()
    except KeyboardInterrupt:
        try:
            again = input("\nWould you like to try again?\nEnter a location (leave empty for current location):")
            get_forecast(again)
            get_history()
        except:
            print('\nProgram Terminated')
            sys.exit(0)
    except Exception as e:
        raise e
        print("An unexpected error occurred.", e)
        sys.exit(1)

if __name__ == '__main__':
    main()