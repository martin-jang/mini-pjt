// 교육용 더미 데이터입니다. 이 파일은 Legacy2Next가 결정적으로 생성합니다 (LLM 작성 금지).

export const listData: Record<string, { rows: Record<string, string>[]; details: Record<string, { label: string; value: string }> }> = {
  "activity": {
    "rows": [
      {
        "date": "12-11-2025",
        "transaction": "Check # 1111",
        "debit": "",
        "credit": "$300.00"
      },
      {
        "date": "12-11-2025",
        "transaction": "Check # 1111",
        "debit": "",
        "credit": "$337.00"
      },
      {
        "date": "12-11-2025",
        "transaction": "Check # 1111",
        "debit": "",
        "credit": "$374.00"
      }
    ],
    "details": {
      "accountNumber": {
        "label": "Account Number",
        "value": "10001"
      },
      "accountType": {
        "label": "Account Type",
        "value": "CHECKING"
      }
    }
  },
  "findtrans": {
    "rows": [
      {
        "date": "",
        "transaction": "",
        "debit": "",
        "credit": ""
      },
      {
        "date": "",
        "transaction": "",
        "debit": "",
        "credit": ""
      },
      {
        "date": "",
        "transaction": "",
        "debit": "",
        "credit": ""
      }
    ],
    "details": {}
  },
  "overview": {
    "rows": [
      {
        "account": "10001",
        "balance": "-$2250.00",
        "availableAmount": "$0.00"
      },
      {
        "account": "10002",
        "balance": "-$2287.00",
        "availableAmount": "$37.00"
      },
      {
        "account": "10003",
        "balance": "-$2324.00",
        "availableAmount": "$74.00"
      }
    ],
    "details": {}
  },
  "transaction": {
    "rows": [],
    "details": {
      "transactionId": {
        "label": "Transaction ID",
        "value": "10001"
      },
      "date": {
        "label": "Date",
        "value": "12-11-2025"
      }
    }
  }
}

export const optionData: Record<string, Record<string, string[]>> = {
  "billpay": {
    "fromaccountid": [
      "10001",
      "10002",
      "10003"
    ]
  },
  "lookup": {},
  "openaccount": {
    "type": [
      "CHECKING",
      "SAVINGS"
    ],
    "fromaccountid": [
      "10001",
      "10002",
      "10003"
    ]
  },
  "register": {},
  "requestloan": {
    "fromaccountid": [
      "10001",
      "10002",
      "10003"
    ]
  },
  "transfer": {
    "fromaccountid": [
      "10001",
      "10002",
      "10003"
    ],
    "toaccountid": [
      "10004",
      "10005",
      "10006"
    ]
  },
  "updateprofile": {}
}
