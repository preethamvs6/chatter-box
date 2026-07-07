pipeline {
    agent any

    environment {
        // Replace 'your-dockerhub-username' with your actual Docker Hub or local registry registry username
        DOCKER_IMAGE = 'your-dockerhub-username/chatterbox:latest'
    }

    stages {
        stage('1. Build Image') {
            steps {
                echo 'Building container image...'
                sh "docker build -t ${DOCKER_IMAGE} ."
            }
        }

        stage('2. Push Registry') {
            steps {
                echo 'Authenticating and pushing image...'
                // To authenticate, configure a Jenkins Credential with ID 'docker-hub-credentials'
                // withCredentials([usernamePassword(credentialsId: 'docker-hub-credentials', usernameVariable: 'USER', passwordVariable: 'PASS')]) {
                //     sh "docker login -u ${USER} -p ${PASS}"
                //     sh "docker push ${DOCKER_IMAGE}"
                // }
                echo 'Skipped credentials check. Enable auth block in production.'
            }
        }

        stage('3. Deploy K8s') {
            steps {
                echo 'Deploying application to Kubernetes cluster...'
                sh "kubectl apply -f k8s-deployment.yaml"
                
                echo 'Waiting for deployment to complete...'
                sh "kubectl rollout status deployment/chatterbox"
            }
        }
    }
}
