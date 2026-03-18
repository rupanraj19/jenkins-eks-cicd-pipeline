from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>Jenkins EKS CI/CD Pipeline — v2 Running! (testing webhook)</h1>'

@app.route('/health')
def health():
    return {'status': 'healthy'}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
