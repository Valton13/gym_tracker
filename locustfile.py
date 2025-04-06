from locust import HttpUser, TaskSet, task

class UserBehavior(TaskSet):
    @task(1)
    def index(self):
        self.client.get("/")

    @task(2)
    def login(self):
        self.client.post("/login", {
            "username": "testuser",
            "password": "testpass"
        })

class WebsiteUser(HttpUser):
    tasks = [UserBehavior]
    min_wait = 1000
    max_wait = 2000