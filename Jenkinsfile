pipeline {
    agent any

    environment {
        AWS_REGION        = 'us-east-1'
        ECR_REPO          = '995004088219.dkr.ecr.us-east-1.amazonaws.com/flask-cicd-app'
        IMAGE_TAG         = "v${BUILD_NUMBER}"
        CLUSTER_NAME      = 'jenkins-cicd-cluster'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                sh """
                    docker build -t ${ECR_REPO}:${IMAGE_TAG} .
                    docker tag ${ECR_REPO}:${IMAGE_TAG} ${ECR_REPO}:latest
                """
            }
        }

        stage('Push to ECR') {
            steps {
                withCredentials([[
                    $class: 'AmazonWebServicesCredentialsBinding',
                    credentialsId: 'aws-credentials'
                ]]) {
                    sh """
                        aws ecr get-login-password --region ${AWS_REGION} | \
                        docker login --username AWS --password-stdin ${ECR_REPO}
                        docker push ${ECR_REPO}:${IMAGE_TAG}
                        docker push ${ECR_REPO}:latest
                    """
                }
            }
        }

        stage('Deploy to EKS') {
            steps {
                sh """
                    aws eks update-kubeconfig --name ${CLUSTER_NAME} --region ${AWS_REGION}
                    sed 's|IMAGE_PLACEHOLDER|${ECR_REPO}:${IMAGE_TAG}|g' k8s/deployment.yaml | kubectl apply -f -
                    kubectl apply -f k8s/service.yaml
                    kubectl rollout status deployment/flask-app
                """
            }
        }

    }

    post {
        success {
            echo 'Pipeline completed successfully! Flask app deployed to EKS.'
        }
        failure {
            echo 'Pipeline failed. Check logs above.'
        }
    }
}