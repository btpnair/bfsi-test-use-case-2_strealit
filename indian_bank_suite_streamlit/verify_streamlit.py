from pathlib import Path
from streamlit.testing.v1 import AppTest
p = str(Path(__file__).resolve().parent / 'streamlit_app.py')
def check(at):
    assert not at.exception, [x.message for x in at.exception]
    return at

def button(at, label):
    matches=[b for b in at.button if b.label==label]
    assert len(matches)==1, (label,[b.label for b in at.button])
    return check(matches[0].click().run())

def login(at, uid, password):
    at.selectbox[0].set_value(uid)
    at.text_input[0].set_value(password)
    at.checkbox[0].check()
    return button(at,'Sign in')

at=check(AppTest.from_file(p,default_timeout=30).run())
assert len(at.table)==1
at.text_input[0].set_value('wrong')
at.checkbox[0].check()
button(at,'Sign in')
assert any('Incorrect' in e.value for e in at.error)
login(at,'operator','Operator-2026!')
for module in ['onboarding','property','leads','grievance','str']:
    check(at.sidebar.selectbox[0].set_value(module).run())
    assert len(at.metric)==7
    assert len(at.tabs)==5
# Existing standard case: prepare -> review, then independent sign-off.
check(at.sidebar.selectbox[0].set_value('onboarding').run())
case=next(s for s in at.selectbox if s.label=='Open case')
check(case.set_value('ONBOARDING-DEMO-001').run())
def action(at, name):
    next(s for s in at.selectbox if s.label=='Action').set_value(name)
    at.multiselect[0].set_value(['KYC-ID-01'])
    next(t for t in at.text_area if t.label.startswith('Review rationale')).set_value('Checked the synthetic evidence and reviewed the case findings.')
    button(at,'Review change')
    assert any(s.value=='Review proposed change' for s in at.subheader)
    button(at,'Confirm change')
action(at,'prepare')
action(at,'request_review')
assert at.session_state.engine.store.case('ONBOARDING-DEMO-001',['onboarding'])['state']=='PENDING_REVIEW'
button(at,'Sign out / switch persona')
login(at,'reviewer','Reviewer-2026!')
check(next(s for s in at.selectbox if s.label=='Open case').set_value('ONBOARDING-DEMO-001').run())
action(at,'approve')
assert at.session_state.engine.store.case('ONBOARDING-DEMO-001',['onboarding'])['state']=='READY_FOR_CBS_INTEGRATION'
# Each new visitor has an independent database.
other=check(AppTest.from_file(p,default_timeout=30).run())
assert other.session_state.engine.store.case('ONBOARDING-DEMO-001',['onboarding'])['state']=='NEW'
assert other.session_state.workspace.name != at.session_state.workspace.name
# Maker creation with cancel and confirm.
button(at,'Sign out / switch persona')
login(at,'operator','Operator-2026!')
next(t for t in at.text_input if t.label=='Case title').set_value('Streamlit smoke test')
next(t for t in at.text_area if t.label.startswith('Intake rationale')).set_value('Create a fictional case for workflow testing.')
button(at,'Review new case')
button(at,'Cancel change')
next(t for t in at.text_input if t.label=='Case title').set_value('Streamlit smoke test')
next(t for t in at.text_area if t.label.startswith('Intake rationale')).set_value('Create a fictional case for workflow testing.')
button(at,'Review new case')
button(at,'Confirm change')
assert len(at.session_state.engine.store.cases(['onboarding']))==4
# Idle expiry clears identity and pending reviews.
at.session_state.last_seen=0
check(at.run())
assert any(s.value=='Choose a demo persona' for s in at.subheader)
print('PASS: login, all 5 workflows, reviewed actions, independent approval, isolation, intake/cancel, expiry')
