"""Public consumer integration checks on disposable SQLite only."""
import importlib,json,sqlite3
import pytest

@pytest.fixture
def fixture(tmp_path,monkeypatch):
    monkeypatch.setenv('INARENA_DB_PATH',str(tmp_path/'consumer.sqlite3'))
    monkeypatch.setenv('INARENA_DATABASE_URL','')
    from app import db,service
    importlib.reload(db);importlib.reload(service);db.ensure_schema()
    table=service.create_table('shared corruption fixture')['id']
    with db.transaction() as conn:
        conn.execute('UPDATE runtime_tables SET cash_buyin_min=1 WHERE id=?',(table,))
    for seat in (1,3,6):service.join_table(table,f'p{seat}',seat,1000)
    service.start_hand(table,button_seat=1)
    return db,service,table

@pytest.mark.parametrize('mutation',[{'mechanics_version':'999'}, {'pot':151}, {'shared_initial_stacks':None}])
def test_persisted_contract_corruption_rejected_atomically(fixture,mutation):
    db,service,table=fixture
    with db.transaction() as conn:
        state=json.loads(conn.execute('SELECT state_json FROM active_hands WHERE table_id=?',(table,)).fetchone()['state_json'])
        state.update(mutation)
        conn.execute('UPDATE active_hands SET state_json=? WHERE table_id=?',(json.dumps(state),table))
    def snapshot():
        with db.transaction() as conn:
            return tuple(tuple(row) for row in conn.execute('SELECT * FROM runtime_seats').fetchall()),conn.execute('SELECT state_json FROM active_hands WHERE table_id=?',(table,)).fetchone()['state_json'],conn.execute('SELECT count(*) AS n FROM hand_actions').fetchone()['n']
    before=snapshot()
    with pytest.raises(service.ConflictError):service.submit_player_action(table,'p1','call',0)
    assert snapshot()==before

def test_replay_rebuild_and_integer_action(fixture):
    db,service,table=fixture
    service.submit_player_action(table,'p1','raise',0,amount=200)
    with db.transaction() as conn:
        row=conn.execute('SELECT hand_id,state_json FROM active_hands WHERE table_id=?',(table,)).fetchone()
        state=json.loads(row['state_json'])
        hand,ids,seats=service.shared_mechanics.rebuild(conn,row['hand_id'],state)
        assert ids==('p1','p3','p6') and seats==(1,3,6)
        assert hand.current_bet_units==200 and hand.players[0].stack_units==800
        assert hand.last_acted_bet[0]==200
        assert state['mechanics_version']=='0.2.2-candidate'
        assert 'hole' not in state and 'remaining_cards' not in state
