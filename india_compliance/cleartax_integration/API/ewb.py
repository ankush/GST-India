import frappe
from india_compliance.cleartax_integration.utils import success_response, error_response, response_error_handling, response_logger,get_dict
from frappe import *
import json
import requests

@frappe.whitelist()
def generate_e_waybill_by_irn(**kwargs):
    try:
        invoice = frappe.get_doc('Sales Invoice',kwargs.get('invoice'))
        item_list = []
        gst_settings_accounts = frappe.get_all("GST Account",
                filters={'company':invoice.company},
                fields=["cgst_account", "sgst_account", "igst_account", "cess_account"])
        for row in invoice.items:
            item_list.append(get_dict('Item',row.item_code))
        delivery_note = get_delivery_note(invoice)
        data = {
            'invoice': invoice.as_dict(),
            'customer': get_dict('Customer',invoice.customer),
            'billing_address': get_dict('Address',invoice.company_address),
            'customer_address': get_dict('Address',invoice.customer_address),
            'shipping_address': get_dict('Address',invoice.shipping_address_name),
            'dispatch_address': get_dict('Address',invoice.dispatch_address_name),
            'item_list': item_list,
            'gst_accounts':gst_settings_accounts,
            'delivery_note': delivery_note,
            'transporter': get_dict('Supplier',delivery_note.transporter)
       }
        dispatch_address = frappe.get_doc("Address",invoice.dispatch_address_name)
        return create_ewb_request(invoice,dispatch_address.gstin,data)
    except Exception as e:
        frappe.logger('cleartax').exception(e)
        return error_response(e)


def create_ewb_request(inv,gstin,data):
    try:
        settings = frappe.get_doc('Cleartax Settings')
        url = settings.host_url
        url+= "/api/method/cleartax.cleartax.API.ewb.generate_e_waybill_by_irn"
        headers = {
            'sandbox': str(settings.sandbox),
            'Content-Type': 'application/json'
        }
        if settings.enterprise:
            if settings.sandbox:
                headers['auth_token'] = settings.sandbox_auth_token
            else:
                headers['auth_token'] = settings.production_auth_token
        data = json.dumps(data, indent=4, sort_keys=False, default=str)
        response = requests.request(
            "POST", url, headers=headers, data=data)
        response = response.json()['message']
        if response.get('error'):
            return error_response(response.get('error'))
        response_status = response['msg']
        response_logger(data,response['response'],"GENERATE EWB BY IRN","Sales Invoice",inv.name,
                        response_status)
        if response_status == "Success":
            return store_ewb_details(inv.name,data,response['response'][0])
        return response_error_handling(response['response'])
    except Exception as e:
        frappe.logger('cleartax').exception(e)
        return error_response(e)



@frappe.whitelist()
def ewb_without_irn(**kwargs):
    try:
        delivery_note = frappe.get_doc('Delivery Note',kwargs.get('delivery_note'))
        item_list = []
        gst_settings_accounts = frappe.get_all("GST Account",
                filters={'company':delivery_note.company},
                fields=["cgst_account", "sgst_account", "igst_account", "cess_account"])
        for row in delivery_note.items:
            item_list.append(get_dict('Item',row.item_code))
        data = {
            'delivery_note':  delivery_note.as_dict(),
            'billing_address': get_dict('Address',delivery_note.company_address),
            'customer_address': get_dict('Address',delivery_note.customer_address),
            'shipping_address': get_dict('Address',delivery_note.shipping_address_name),
            'dispatch_address': get_dict('Address',delivery_note.dispatch_address_name),
            'transporter': get_dict('Supplier',delivery_note.transporter),
            'item_list': item_list,
            'gst_accounts':gst_settings_accounts
        }
        return ewb_without_irn_request(kwargs.get('delivery_note'),data)
    except Exception as e:
        frappe.logger('cleartax').exception(e)
        return error_response(e)

def ewb_without_irn_request(delivery_note,data):
    try:
        settings = frappe.get_doc('Cleartax Settings')
        url = settings.host_url
        url+= "/api/method/cleartax.cleartax.API.ewb.ewb_without_irn"
        headers = {
            'sandbox': str(settings.sandbox),
            'Content-Type': 'application/json'
        }
        if settings.enterprise:
            if settings.sandbox:
                headers['auth_token'] = settings.sandbox_auth_token
            else:
                headers['auth_token'] = settings.production_auth_token
        data = json.dumps(data, indent=4, sort_keys=False, default=str)
        response = requests.request(
            "POST", url, headers=headers, data=data)
        response = response.json()['message']
        if response.get('error'):
            return error_response(response.get('error'))
        response_status = "Failed"
        if response.get('govt_response').get('Success') =='Y':
            response_status = "Success"
        response_logger(data,response,"GENERATE EWB WITHOUT IRN","Delivery Note",delivery_note,
                        response_status)
        return store_ewb_details_dn(delivery_note,data,response)
    except Exception as e:
        frappe.logger('cleartax').exception(e)
        return error_response(e) 

def store_ewb_details_dn(delivery_note,data,response):
    if response.get('govt_response').get('Success') =='Y':
        frappe.db.set_value('Delivery Note',delivery_note,'ewaybill', response.get('govt_response').get('EwbNo'))
        frappe.db.set_value('Delivery Note',delivery_note,'ewb_date', response.get('govt_response').get('EwbDt'))
        frappe.db.set_value('Delivery Note',delivery_note,'ewb_valid_till', response.get('govt_response').get('EwbValidTill'))
        frappe.db.set_value('Delivery Note',delivery_note,'ewb_trans_id', response.get('transaction_id'))
        return success_response()
    return response_error_handling(response)



@frappe.whitelist()
def update_ewb_partb(**kwargs):
    try:
        delivery_note = frappe.get_doc('Delivery Note', kwargs.get('delivery_note'))
        data = {
            'data' : json.loads(kwargs.get('data')),
            'delivery_note': delivery_note.as_dict(),
            'dispatch_address': get_dict('Address', delivery_note.dispatch_address_name),
            'shipping_address': get_dict('Address',delivery_note.shipping_address_name)
        }
        return partb_request(data,kwargs.get('delivery_note'))
    except Exception as e:
        frappe.logger('cleartax').exception(e)
        return error_response(e)


def partb_request(data,dn):
    try:
        settings = frappe.get_doc('Cleartax Settings')
        url = settings.host_url
        url+= "/api/method/cleartax.cleartax.API.ewb.update_ewb_partb"
        headers = {
            'sandbox': str(settings.sandbox),
            'Content-Type': 'application/json'
        }
        if settings.enterprise:
            if settings.sandbox:
                headers['auth_token'] = settings.sandbox_auth_token
            else:
                headers['auth_token'] = settings.production_auth_token
        data = json.dumps(data, indent=4, sort_keys=False, default=str)    
        response = requests.request(
            "POST", url, headers=headers, data=data)
        response = response.json()['message']
        if response.get('error'):
            return error_response(response.get('error'))
        frappe.logger('cleartax').exception(response)
        response_status = response['status']
        if response_status == 'Success':
            frappe.db.set_value('Delivery Note',dn,'update_partb',1)
            return success_response(response['response'])
        else:
            return response_error_handling(response['response'])
    except Exception as e:
        frappe.logger('cleartax').exception(e)
        return error_response(e)

    



@frappe.whitelist()
def cancel_ewb(**kwargs):
    try:
        settings = frappe.get_doc('Cleartax Settings')
        url = settings.host_url
        url+= "/api/method/cleartax.cleartax.API.ewb.cancel_ewb"
        headers = {
            'sandbox': str(settings.sandbox),
            'Content-Type': 'application/json'
        }
        if settings.enterprise:
            if settings.sandbox:
                headers['auth_token'] = settings.sandbox_auth_token
            else:
                headers['auth_token'] = settings.production_auth_token
        invoice = frappe.get_doc('Sales Invoice', kwargs.get('invoice'))
        gstin = frappe.get_value('Address', invoice.company_address,'gstin')
        data = json.loads(kwargs.get('data'))
        data = {
                    "ewbNo": invoice.ewaybill,
                    "cancelRsnCode": data.get('reason'),
                    "cancelRmrk" : data.get('remarks'),
                    'gstin': gstin,
                    'invoice': invoice.name
                }
        return cancel_ewb_request(headers,url,data,invoice.name)
    except Exception as e:
        frappe.logger('cleartax').exception(e)
        return error_response(e)

@frappe.whitelist()
def cancel_ewb_dn(**kwargs):
    try:
        settings = frappe.get_doc('Cleartax Settings')
        url = settings.host_url
        url+= "/api/method/cleartax.cleartax.API.ewb.cancel_ewb"
        headers = {
            'sandbox': str(settings.sandbox),
            'Content-Type': 'application/json'
        }
        if settings.enterprise:
            if settings.sandbox:
                headers['auth_token'] = settings.sandbox_auth_token
            else:
                headers['auth_token'] = settings.production_auth_token
        deliver_note = frappe.get_doc('Delivery Note', kwargs.get('delivery_note'))
        gstin = frappe.get_value('Address', deliver_note.dispatch_address_name,'gstin')
        data = json.loads(kwargs.get('data'))
        data = {
                    "ewbNo": deliver_note.ewaybill,
                    "cancelRsnCode":data.get('reason'),
                    "cancelRmrk" : data.get('remarks'),
                    "gstin":gstin
                }
        return cancel_ewb_request(headers,url,data,delivery_note=kwargs.get('delivery_note'))
    except Exception as e:
        frappe.logger('cleartax').exception(e)
        return error_response(e)
        




def store_ewb_details(inv,data,response):
    try:
        response = response.get('govt_response')
        if response.get('Status') == "GENERATED":
            frappe.db.set_value('Sales Invoice',inv,'ewaybill', response.get('EwbNo'))
            frappe.db.set_value('Sales Invoice',inv,'ewb_date', response.get('EwbDt'))
            frappe.db.set_value('Sales Invoice',inv,'eway_bill_validity', response.get('EwbValidTill'))
            return success_response(response)
        return response_error_handling(response)
    except Exception as e:
        frappe.logger('cleartax').exception(e)
        return error_response(e)




def cancel_ewb_request(headers,url,data,invoice=None,delivery_note=None):
    data = json.dumps(data, indent=4, sort_keys=False, default=str)
    response = requests.request(
            "POST", url, headers=headers, data=data)
    response = response.json()['message']
    doctype = "Sales Invoice" if invoice else "Delivery Note"
    docname = invoice if invoice else delivery_note
    response_status = "Failed"
    if response.get('error'):
        return error_response(response.get('error'))
    if response.get('ewbStatus') == 'CANCELLED':
        response_status = "Success"
        response_logger(data,response,"CANCEL EWB",doctype,docname,response_status)
        if invoice:
            frappe.db.set_value('Sales Invoice',invoice,'eway_bill_cancelled',1)
        else:
            frappe.db.set_value('Delivery Note',delivery_note,'eway_bill_cancelled',1)
        return success_response(data=response)
    return response_error_handling(response) 



def get_delivery_note(doc):
        delivery_note = frappe.get_value('Delivery Note Item',{"against_sales_invoice":doc.name},"parent")
        if delivery_note:
            return frappe.get_doc('Delivery Note',delivery_note).as_dict()
        delivery_note = frappe.get_value('Sales Invoice Item',{"parent":doc.name},"delivery_note")
        if delivery_note:
            return frappe.get_doc('Delivery Note',delivery_note).as_dict()
        return {}

@frappe.whitelist()
def bulk_ewb(**kwargs):
    try:
        data = json.loads(kwargs.get('data'))
        for i in data:
            frappe.enqueue("cleartax.cleartax.API.ewb.generate_e_waybill_by_irn",**{'invoice':i})
    except Exception as e:
        frappe.logger('sfa_online').exception(e)