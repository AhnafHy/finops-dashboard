import boto3
import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
ce = boto3.client('ce', region_name='us-east-1')

TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'finops-cost-data')
BUDGET_THRESHOLD = float(os.environ.get('MONTHLY_BUDGET', '50.0'))

def get_cost_data(start_date, end_date):
    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='DAILY',
        Metrics=['BlendedCost', 'UnblendedCost', 'UsageQuantity'],
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SERVICE'}
        ]
    )
    return response['ResultsByTime']

def store_cost_data(table, results):
    stored_count = 0
    with table.batch_writer() as batch:
        for day_result in results:
            date = day_result['TimePeriod']['Start']
            total_cost = Decimal('0')
            
            for group in day_result['Groups']:
                service = group['Keys'][0]
                cost = Decimal(str(group['Metrics']['BlendedCost']['Amount']))
                unit = group['Metrics']['BlendedCost']['Unit']
                
                if cost > Decimal('0'):
                    batch.put_item(Item={
                        'pk': f"COST#{date}",
                        'sk': f"SERVICE#{service}",
                        'date': date,
                        'service': service,
                        'blended_cost': cost,
                        'unit': unit,
                        'collected_at': datetime.now(timezone.utc).isoformat()
                    })
                    total_cost += cost
                    stored_count += 1
            
            # Store daily total
            batch.put_item(Item={
                'pk': f"COST#{date}",
                'sk': 'TOTAL',
                'date': date,
                'service': 'TOTAL',
                'blended_cost': total_cost,
                'unit': 'USD',
                'collected_at': datetime.now(timezone.utc).isoformat()
            })
    
    return stored_count

def check_budget(table):
    today = datetime.now(timezone.utc)
    month_start = today.replace(day=1).strftime('%Y-%m-%d')
    
    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': month_start,
            'End': today.strftime('%Y-%m-%d')
        },
        Granularity='MONTHLY',
        Metrics=['BlendedCost']
    )
    
    if response['ResultsByTime']:
        mtd_cost = float(response['ResultsByTime'][0]['Total']['BlendedCost']['Amount'])
        days_elapsed = today.day
        days_in_month = 30
        projected_cost = (mtd_cost / days_elapsed) * days_in_month
        
        table.put_item(Item={
            'pk': f"BUDGET#{today.strftime('%Y-%m')}",
            'sk': 'PROJECTION',
            'month': today.strftime('%Y-%m'),
            'mtd_cost': Decimal(str(round(mtd_cost, 4))),
            'projected_monthly_cost': Decimal(str(round(projected_cost, 4))),
            'budget_threshold': Decimal(str(BUDGET_THRESHOLD)),
            'is_over_budget': projected_cost > BUDGET_THRESHOLD,
            'collected_at': datetime.now(timezone.utc).isoformat()
        })
        
        return mtd_cost, projected_cost

def lambda_handler(event, context):
    table = dynamodb.Table(TABLE_NAME)
    
    end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
    
    print(f"Collecting cost data from {start_date} to {end_date}")
    results = get_cost_data(start_date, end_date)
    stored = store_cost_data(table, results)
    print(f"Stored {stored} cost records")
    
    mtd_cost, projected = check_budget(table)
    print(f"MTD cost: ${mtd_cost:.2f} | Projected: ${projected:.2f} | Budget: ${BUDGET_THRESHOLD:.2f}")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'records_stored': stored,
            'mtd_cost': round(mtd_cost, 2),
            'projected_monthly_cost': round(projected, 2),
            'over_budget': projected > BUDGET_THRESHOLD
        })
    }