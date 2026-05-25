"""
Ethiopian Calendar Conversion Utilities
Converts between Gregorian and Ethiopian calendars
"""

from datetime import date, datetime, timedelta
from typing import Tuple, Dict, List
from decimal import Decimal


class EthiopianCalendar:
    """Ethiopian Calendar Conversion and Utilities"""
    
    # Ethiopian month names in Amharic and English
    ETHIOPIAN_MONTHS = {
        1: {'amharic': 'Meskerem', 'english': 'September'},
        2: {'amharic': 'Tikimt', 'english': 'October'},
        3: {'amharic': 'Hidar', 'english': 'November'},
        4: {'amharic': 'Tahsas', 'english': 'December'},
        5: {'amharic': 'Tir', 'english': 'January'},
        6: {'amharic': 'Yekatit', 'english': 'February'},
        7: {'amharic': 'Megabit', 'english': 'March'},
        8: {'amharic': 'Miazia', 'english': 'April'},
        9: {'amharic': 'Genbot', 'english': 'May'},
        10: {'amharic': 'Sene', 'english': 'June'},
        11: {'amharic': 'Hamle', 'english': 'July'},
        12: {'amharic': 'Nehase', 'english': 'August'},
        13: {'amharic': 'Pagume', 'english': 'Pagume'},
    }
    
    # Days in each Ethiopian month (13 months, 13th has 5 or 6 days)
    DAYS_IN_MONTH = {
        1: 30, 2: 30, 3: 30, 4: 30, 5: 30, 6: 30,
        7: 30, 8: 30, 9: 30, 10: 30, 11: 30, 12: 30,
        13: 5,  # Pagume has 5 days in normal year
    }
    
    # Ethiopian New Year (Meskerem 1) in Gregorian
    ETHIOPIAN_NEW_YEAR_NORMAL = (9, 11)  # September 11
    ETHIOPIAN_NEW_YEAR_LEAP = (9, 12)    # September 12 (before Gregorian leap year)
    
    @classmethod
    def is_ethiopian_leap_year(cls, ethiopian_year: int) -> bool:
        """Check if Ethiopian year is a leap year (Pagume has 6 days)"""
        # Ethiopian leap year occurs every 4 years without exception
        return ethiopian_year % 4 == 3
    
    @classmethod
    def get_days_in_ethiopian_month(cls, ethiopian_year: int, ethiopian_month: int) -> int:
        """Get number of days in Ethiopian month"""
        if ethiopian_month == 13 and cls.is_ethiopian_leap_year(ethiopian_year):
            return 6
        return cls.DAYS_IN_MONTH.get(ethiopian_month, 30)
    
    @classmethod
    def gregorian_to_ethiopian(cls, gregorian_date: date) -> Tuple[int, int, int]:
        """
        Convert Gregorian date to Ethiopian date
        Returns: (ethiopian_year, ethiopian_month, ethiopian_day)
        """
        # Ethiopian calendar is approximately 7-8 years behind Gregorian
        # Ethiopian New Year is September 11/12
        
        # Reference date: Ethiopian New Year 2016 = September 11, 2023
        REF_ETHIOPIAN_YEAR = 2016
        REF_GREGORIAN = date(2023, 9, 11)
        
        # Calculate days difference
        days_diff = (gregorian_date - REF_GREGORIAN).days
        
        # Calculate Ethiopian year
        ethiopian_year = REF_ETHIOPIAN_YEAR + (days_diff // 365)
        
        # Calculate remaining days
        remaining_days = days_diff % 365
        
        # If negative, we're before the reference date
        if remaining_days < 0:
            ethiopian_year -= 1
            remaining_days += 365
        
        # Calculate month and day
        ethiopian_month = 1
        ethiopian_day = remaining_days + 1
        
        for month in range(1, 14):
            days_in_month = cls.get_days_in_ethiopian_month(ethiopian_year, month)
            if ethiopian_day <= days_in_month:
                ethiopian_month = month
                break
            ethiopian_day -= days_in_month
        
        return (ethiopian_year, ethiopian_month, ethiopian_day)
    
    @classmethod
    def ethiopian_to_gregorian(cls, ethiopian_year: int, ethiopian_month: int, ethiopian_day: int) -> date:
        """
        Convert Ethiopian date to Gregorian date
        Returns: Gregorian date
        """
        # Reference date: Ethiopian New Year 2016 = September 11, 2023
        REF_ETHIOPIAN_YEAR = 2016
        REF_GREGORIAN = date(2023, 9, 11)
        
        # Calculate days from Ethiopian New Year to target date
        days_from_new_year = ethiopian_day - 1
        
        for month in range(1, ethiopian_month):
            days_from_new_year += cls.get_days_in_ethiopian_month(ethiopian_year, month)
        
        # Calculate year difference
        year_diff = ethiopian_year - REF_ETHIOPIAN_YEAR
        total_days = year_diff * 365 + days_from_new_year
        
        # Calculate Gregorian date
        gregorian_date = REF_GREGORIAN + timedelta(days=total_days)
        
        return gregorian_date
    
    @classmethod
    def get_ethiopian_month_name(cls, ethiopian_month: int, language: str = 'english') -> str:
        """Get Ethiopian month name in specified language"""
        month_info = cls.ETHIOPIAN_MONTHS.get(ethiopian_month, {})
        return month_info.get(language, month_info.get('english', ''))
    
    @classmethod
    def format_ethiopian_date(cls, ethiopian_year: int, ethiopian_month: int, ethiopian_day: int, 
                             language: str = 'english') -> str:
        """Format Ethiopian date as string"""
        month_name = cls.get_ethiopian_month_name(ethiopian_month, language)
        return f"{month_name} {ethiopian_day}, {ethiopian_year}"
    
    @classmethod
    def get_ethiopian_fiscal_year(cls, gregorian_date: date) -> int:
        """
        Get Ethiopian fiscal year for a Gregorian date
        Ethiopian fiscal year starts on Meskerem 1 (September 11/12)
        """
        ethiopian_date = cls.gregorian_to_ethiopian(gregorian_date)
        ethiopian_year, ethiopian_month, _ = ethiopian_date
        
        # If we're in Pagume (month 13), we're at the end of the fiscal year
        if ethiopian_month == 13:
            return ethiopian_year
        
        return ethiopian_year
    
    @classmethod
    def get_ethiopian_fiscal_year_range(cls, ethiopian_fiscal_year: int) -> Tuple[date, date]:
        """
        Get Gregorian date range for Ethiopian fiscal year
        Returns: (start_date, end_date)
        """
        start_date = cls.ethiopian_to_gregorian(ethiopian_fiscal_year, 1, 1)
        
        # End date is Pagume last day of the fiscal year
        end_day = cls.get_days_in_ethiopian_month(ethiopian_fiscal_year, 13)
        end_date = cls.ethiopian_to_gregorian(ethiopian_fiscal_year, 13, end_day)
        
        return (start_date, end_date)
    
    @classmethod
    def get_ethiopian_quarter(cls, ethiopian_month: int) -> int:
        """Get Ethiopian quarter (1-4) for Ethiopian month"""
        if ethiopian_month <= 3:
            return 1
        elif ethiopian_month <= 6:
            return 2
        elif ethiopian_month <= 9:
            return 3
        elif ethiopian_month <= 12:
            return 4
        else:  # Pagume
            return 4


class EthiopianHolidays:
    """Ethiopian Holidays and Observances"""
    
    # Ethiopian Orthodox holidays (Ethiopian calendar dates)
    ETHIOPIAN_HOLIDAYS = {
        'ethiopian_christmas': {
            'ethiopian_month': 4,
            'ethiopian_day': 28,
            'name_amharic': 'Genna',
            'name_english': 'Ethiopian Christmas',
            'is_public': True,
        },
        'epiphany': {
            'ethiopian_month': 5,
            'ethiopian_day': 19,
            'name_amharic': 'Timket',
            'name_english': 'Epiphany',
            'is_public': True,
        },
        'good_friday': {
            'ethiopian_month': 8,
            'day_offset': -2,  # 2 days before Easter
            'name_amharic': 'Siklet',
            'name_english': 'Good Friday',
            'is_public': True,
        },
        'easter': {
            'ethiopian_month': 8,
            'day_offset': 0,  # Calculated based on Orthodox Easter
            'name_amharic': 'Fasika',
            'name_english': 'Easter',
            'is_public': True,
        },
        'ethiopian_new_year': {
            'ethiopian_month': 1,
            'ethiopian_day': 1,
            'name_amharic': 'Enkutatash',
            'name_english': 'Ethiopian New Year',
            'is_public': True,
        },
        'finding_of_true_cross': {
            'ethiopian_month': 9,
            'ethiopian_day': 26,
            'name_amharic': 'Meskel',
            'name_english': 'Finding of the True Cross',
            'is_public': True,
        },
    }
    
    # National holidays (Gregorian calendar dates)
    NATIONAL_HOLIDAYS = {
        'labor_day': {
            'gregorian_month': 5,
            'gregorian_day': 1,
            'name_amharic': 'Workers Day',
            'name_english': 'Labor Day',
            'is_public': True,
        },
        'victory_day': {
            'gregorian_month': 5,
            'gregorian_day': 28,
            'name_amharic': 'Victory Day',
            'name_english': 'Victory Day',
            'is_public': True,
        },
        'downfall_of_derg': {
            'gregorian_month': 5,
            'gregorian_day': 28,
            'name_amharic': 'Downfall of Derg',
            'name_english': 'Downfall of Derg',
            'is_public': True,
        },
    }
    
    @classmethod
    def get_ethiopian_holiday_date(cls, holiday_key: str, ethiopian_year: int) -> date:
        """Get Gregorian date for Ethiopian holiday in given Ethiopian year"""
        holiday = cls.ETHIOPIAN_HOLIDAYS.get(holiday_key)
        if not holiday:
            return None
        
        ethiopian_month = holiday['ethiopian_month']
        ethiopian_day = holiday['ethiopian_day']
        
        return EthiopianCalendar.ethiopian_to_gregorian(
            ethiopian_year, ethiopian_month, ethiopian_day
        )
    
    @classmethod
    def get_national_holiday_date(cls, holiday_key: str, gregorian_year: int) -> date:
        """Get date for national holiday in given Gregorian year"""
        holiday = cls.NATIONAL_HOLIDAYS.get(holiday_key)
        if not holiday:
            return None
        
        return date(gregorian_year, holiday['gregorian_month'], holiday['gregorian_day'])
    
    @classmethod
    def get_holidays_in_fiscal_year(cls, ethiopian_fiscal_year: int) -> List[Dict]:
        """Get all holidays in Ethiopian fiscal year"""
        holidays = []
        
        # Ethiopian calendar holidays
        for key, holiday in cls.ETHIOPIAN_HOLIDAYS.items():
            holiday_date = cls.get_ethiopian_holiday_date(key, ethiopian_fiscal_year)
            if holiday_date:
                holidays.append({
                    'key': key,
                    'date': holiday_date,
                    'name_amharic': holiday['name_amharic'],
                    'name_english': holiday['name_english'],
                    'is_public': holiday['is_public'],
                    'type': 'ethiopian',
                })
        
        # National holidays (need to check which fall in fiscal year)
        fiscal_start, fiscal_end = EthiopianCalendar.get_ethiopian_fiscal_year_range(ethiopian_fiscal_year)
        
        for key, holiday in cls.NATIONAL_HOLIDAYS.items():
            # Check both current and next Gregorian year
            for year in [fiscal_start.year, fiscal_end.year]:
                holiday_date = cls.get_national_holiday_date(key, year)
                if fiscal_start <= holiday_date <= fiscal_end:
                    holidays.append({
                        'key': key,
                        'date': holiday_date,
                        'name_amharic': holiday['name_amharic'],
                        'name_english': holiday['name_english'],
                        'is_public': holiday['is_public'],
                        'type': 'national',
                    })
        
        # Sort by date
        holidays.sort(key=lambda x: x['date'])
        
        return holidays
    
    @classmethod
    def is_holiday(cls, gregorian_date: date) -> bool:
        """Check if a date is a public holiday"""
        ethiopian_year, ethiopian_month, ethiopian_day = EthiopianCalendar.gregorian_to_ethiopian(gregorian_date)
        
        # Check Ethiopian holidays
        for holiday in cls.ETHIOPIAN_HOLIDAYS.values():
            if (holiday['ethiopian_month'] == ethiopian_month and 
                holiday['ethiopian_day'] == ethiopian_day):
                return True
        
        # Check national holidays
        for holiday in cls.NATIONAL_HOLIDAYS.values():
            if (holiday['gregorian_month'] == gregorian_date.month and 
                holiday['gregorian_day'] == gregorian_date.day):
                return True
        
        return False


class EthiopianDateFormatter:
    """Date formatting utilities for Ethiopian context"""
    
    @classmethod
    def format_gregorian_as_ethiopian(cls, gregorian_date: date, language: str = 'english') -> str:
        """Format Gregorian date showing both calendars"""
        ethiopian_year, ethiopian_month, ethiopian_day = EthiopianCalendar.gregorian_to_ethiopian(gregorian_date)
        
        month_name = EthiopianCalendar.get_ethiopian_month_name(ethiopian_month, language)
        
        if language == 'amharic':
            return f"{month_name} {ethiopian_day}, {ethiopian_year} (EC)"
        else:
            return f"{month_name} {ethiopian_day}, {ethiopian_year} (EC) / {gregorian_date.strftime('%B %d, %Y')} (GC)"
    
    @classmethod
    def format_ethiopian_fiscal_year(cls, ethiopian_fiscal_year: int, language: str = 'english') -> str:
        """Format Ethiopian fiscal year"""
        if language == 'amharic':
            return f"{ethiopian_fiscal_year} ዓ/ም"
        else:
            return f"FY {ethiopian_fiscal_year} EC"
    
    @classmethod
    def get_current_ethiopian_date(cls) -> Tuple[int, int, int]:
        """Get current Ethiopian date"""
        return EthiopianCalendar.gregorian_to_ethiopian(date.today())
    
    @classmethod
    def get_current_ethiopian_fiscal_year(cls) -> int:
        """Get current Ethiopian fiscal year"""
        return EthiopianCalendar.get_ethiopian_fiscal_year(date.today())
