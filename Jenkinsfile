pipeline {
    agent any

    environment {
        // Replace 'your-dockerhub-username' with your actual Docker Hub or registry username
        DOCKER_REGISTRY_USER = 'your-dockerhub-username'
        DOCKER_IMAGE = "${DOCKER_REGISTRY_USER}/chatterbox:${BUILD_NUMBER}"
    }

    stages {
        stage('1. Build Image') {
            steps {
                echo "Building container image: ${DOCKER_IMAGE}..."
                sh "docker build -t ${DOCKER_IMAGE} ."
            }
        }

        stage('2. Push Registry') {
            steps {
                echo 'Authenticating and pushing image...'
                // To authenticate, configure a Jenkins Credential with ID 'docker-hub-credentials'
                withCredentials([usernamePassword(credentialsId: 'docker-hub-credentials', usernameVariable: 'USER', passwordVariable: 'PASS')]) {
                    sh "docker login -u ${USER} -p ${PASS}"
                    sh "docker push ${DOCKER_IMAGE}"
                }
            }
        }

        stage('3. Deploy K8s') {
            steps {
                echo 'Deploying application to Kubernetes cluster...'
                // Use the 'Secret file' credential with ID 'kubeconfig' created in Step 2
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    // Diagnostic info to see what configuration kubectl is using:
                    sh "echo 'KUBECONFIG path is: '\$KUBECONFIG"
                    sh "kubectl config view"
                    
                    // Update the image placeholder in k8s-deployment.yaml to target the newly built tagged image
                    sh "sed -i 's|image: .*|image: ${DOCKER_IMAGE}|g' k8s-deployment.yaml"
                    
                    sh "kubectl apply -f k8s-deployment.yaml"
                    
                    echo 'Waiting for deployment to complete...'
                    sh "kubectl rollout status deployment/chatterbox"
                }
            }
        }
    }
}
