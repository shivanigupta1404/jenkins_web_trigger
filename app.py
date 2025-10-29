from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import requests
from requests.auth import HTTPBasicAuth
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# Jenkins config
JENKINS_URL = "http://172.20.4.91:8080/"
USERNAME = "qualitia"
API_TOKEN = os.getenv('JENKINS_API_TOKEN')

# Define available environments
ENVIRONMENTS = ["DEVMerge1", "QA1", "UAT1"]

def get_jenkins_jobs():
    """Fetch top-level Jenkins jobs"""
    try:
        api_url = f"{JENKINS_URL}/api/json"
        response = requests.get(api_url, auth=HTTPBasicAuth(USERNAME, API_TOKEN))
        response.raise_for_status()
        jobs_data = response.json().get("jobs", [])

        jobs = []
        for job in jobs_data:
            job_api = f"{job['url']}api/json"
            job_resp = requests.get(job_api, auth=HTTPBasicAuth(USERNAME, API_TOKEN))
            if job_resp.status_code == 200:
                job_json = job_resp.json()
                if job_json.get('_class') != 'com.cloudbees.hudson.plugins.folder.Folder':
                    jobs.append({
                        "name": job_json['name'],
                        "description": job_json.get('description', '')
                    })
        return jobs
    except Exception as e:
        print(f"Error fetching jobs: {e}")
        return []

def trigger_build(job_name, user_email):
    crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
    build_url = f"{JENKINS_URL}/job/{job_name}/buildWithParameters"

    try:
        crumb_response = requests.get(crumb_url, auth=HTTPBasicAuth(USERNAME, API_TOKEN))
        crumb_response.raise_for_status()
        crumb_data = crumb_response.json()
        headers = {
            crumb_data['crumbRequestField']: crumb_data['crumb'],
            "Content-Type": "application/x-www-form-urlencoded"
        }

        payload = {'EMAIL': user_email}
        print(f"Triggering job '{job_name}' for user: {user_email}")

        response = requests.post(build_url, auth=HTTPBasicAuth(USERNAME, API_TOKEN), headers=headers, data=payload)

        if response.status_code == 201:
            return True, "Build triggered successfully!"
        else:
            return False, f"Failed to trigger build. Status code: {response.status_code}"
    except Exception as e:
        return False, f"Exception: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html', environments=ENVIRONMENTS)

@app.route('/trigger', methods=['POST'])
def trigger():
    job_name = request.form.get('job')
    user_email = request.form.get('email')
    success, message = trigger_build(job_name, user_email)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('index'))

@app.route('/get-jobs/<env_name>')
def get_jobs(env_name):
    """Fetch jobs filtered by environment suffix"""
    all_jobs = get_jenkins_jobs()
    env_filtered = [job for job in all_jobs if job['name'].lower().endswith(env_name.lower())]
    return jsonify(env_filtered)

@app.route('/job-description/<job_name>')
def job_description(job_name):
    job_url = f"{JENKINS_URL}/job/{job_name}/api/json"
    try:
        response = requests.get(job_url, auth=HTTPBasicAuth(USERNAME, API_TOKEN))
        if response.status_code == 200:
            data = response.json()
            return jsonify({"description": data.get("description", "")})
    except Exception as e:
        print(f"Error fetching description for {job_name}: {e}")
    return jsonify({"description": "Unable to fetch description."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)