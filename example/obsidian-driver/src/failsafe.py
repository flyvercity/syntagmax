# [< id=SRC-002 parent=REQ-002 >>>
def handle_failsafe(event):
    if event == 'LINK_LOSS':
        trigger_rth()


# >]
