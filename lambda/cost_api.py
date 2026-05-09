import boto3
import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'finops-cost-data')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }

def get_daily_costs(table, date):
    result = table.query(
        KeyConditionExpression=Key('pk').eq(f"COST#{date}")
    )
    items = result.get('Items', [])
    services = [i for i in items if i['sk'] != 'TOTAL']
    total = next((i for i in items if i['sk'] == 'TOTAL'), None)
    return {
        'date': date,
        'total_cost': float(total['blended_cost']) if total else 0,
        'services': sorted([{
            'service': i['service'],
            'cost': float(i['blended_cost']),
            'unit': i['unit']
        } for i in services], key=lambda x: x['cost'], reverse=True)
    }

def get_cost_range(table, start_date, end_date):
    from datetime import date as date_type
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    daily_costs = []
    current = start
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        result = table.query(
            KeyConditionExpression=Key('pk').eq(f"COST#{date_str}") & Key('sk').eq('TOTAL')
        )
        items = result.get('Items', [])
        if items:
            daily_costs.append({
                'date': date_str,
                'total_cost': float(items[0]['blended_cost'])
            })
        current += timedelta(days=1)
    
    total = sum(d['total_cost'] for d in daily_costs)
    return {
        'start_date': start_date,
        'end_date': end_date,
        'total_cost': round(total, 4),
        'daily_breakdown': daily_costs
    }

def get_budget_status(table):
    month = datetime.now(timezone.utc).strftime('%Y-%m')
    result = table.query(
        KeyConditionExpression=Key('pk').eq(f"BUDGET#{month}") & Key('sk').eq('PROJECTION')
    )
    items = result.get('Items', [])
    if not items:
        return {'error': 'No budget data available yet'}
    item = items[0]
    return {
        'month': item['month'],
        'mtd_cost': float(item['mtd_cost']),
        'projected_monthly_cost': float(item['projected_monthly_cost']),
        'budget_threshold': float(item['budget_threshold']),
        'is_over_budget': item['is_over_budget'],
        'variance': float(item['projected_monthly_cost']) - float(item['budget_threshold'])
    }

def get_top_services(table, days=7):
    service_totals = {}
    for i in range(days):
        date = (datetime.now(timezone.utc) - timedelta(days=i+1)).strftime('%Y-%m-%d')
        result = table.query(
            KeyConditionExpression=Key('pk').eq(f"COST#{date}")
        )
        for item in result.get('Items', []):
            if item['sk'] != 'TOTAL':
                service = item['service']
                cost = float(item['blended_cost'])
                service_totals[service] = service_totals.get(service, 0) + cost
    
    sorted_services = sorted(service_totals.items(), key=lambda x: x[1], reverse=True)
    return {
        'period_days': days,
        'top_services': [{'service': s, 'total_cost': round(c, 4)} for s, c in sorted_services[:10]]
    }

def lambda_handler(event, context):
    table = dynamodb.Table(TABLE_NAME)
    path = event.get('path', '/')
    method = event.get('httpMethod', 'GET')
    params = event.get('queryStringParameters') or {}
    
    if method == 'GET' and path == '/health':
        return response(200, {'status': 'ok'})
    
    elif method == 'GET' and path == '/costs/daily':
        date = params.get('date', (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d'))
        return response(200, get_daily_costs(table, date))
    
    elif method == 'GET' and path == '/costs/range':
        start = params.get('start', (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d'))
        end = params.get('end', (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d'))
        return response(200, get_cost_range(table, start, end))
    
    elif method == 'GET' and path == '/costs/top-services':
        days = int(params.get('days', 7))
        return response(200, get_top_services(table, days))
    
    elif method == 'GET' and path == '/budget/status':
        return response(200, get_budget_status(table))
    
    return response(404, {'error': 'Endpoint not found'})